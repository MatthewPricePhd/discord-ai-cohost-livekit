"""
Voice audio receiver for disnake.

Reads incoming UDP packets from the Discord voice socket,
decrypts SRTP + DAVE, decodes Opus, and passes PCM to a callback.
"""
import asyncio
import struct
import threading
from typing import Optional, Callable, Dict

import disnake

try:
    import nacl.secret
    has_nacl = True
except ImportError:
    has_nacl = False

try:
    import opuslib
    has_opuslib = True
except ImportError:
    has_opuslib = False

try:
    import dave as _dave
    has_dave = True
except ImportError:
    has_dave = False

from ..config import get_logger

logger = get_logger(__name__)

# RTP header is 12 bytes minimum
RTP_HEADER_SIZE = 12
# Discord voice uses 48kHz stereo
SAMPLE_RATE = 48000
CHANNELS = 2
FRAME_LENGTH_MS = 20
SAMPLES_PER_FRAME = SAMPLE_RATE * FRAME_LENGTH_MS // 1000  # 960
SILENCE_FRAME = b'\xf8\xff\xfe'  # Opus silence


class OpusDecoder:
    """Wraps ctypes-based Opus decoding."""

    def __init__(self):
        self._decoder = None
        self._lib = None
        self._init_decoder()

    def _init_decoder(self):
        """Initialize Opus decoder using ctypes (no opuslib dependency)."""
        import ctypes
        import ctypes.util
        import platform

        # Find opus library
        if platform.system() == "Darwin":
            paths = ["/opt/homebrew/lib/libopus.dylib", "/usr/local/lib/libopus.dylib"]
        elif platform.system() == "Linux":
            paths = ["libopus.so.0", "libopus.so"]
        else:
            paths = ["opus"]

        lib = None
        for path in paths:
            try:
                lib = ctypes.cdll.LoadLibrary(path)
                break
            except OSError:
                continue

        if lib is None:
            # Try ctypes.util
            name = ctypes.util.find_library("opus")
            if name:
                lib = ctypes.cdll.LoadLibrary(name)

        if lib is None:
            raise RuntimeError("Could not find opus library for decoding")

        self._lib = lib

        # opus_decoder_create(Fs, channels, *error) -> OpusDecoder*
        lib.opus_decoder_create.argtypes = [ctypes.c_int, ctypes.c_int, ctypes.POINTER(ctypes.c_int)]
        lib.opus_decoder_create.restype = ctypes.c_void_p

        # opus_decode(decoder, data, len, pcm, frame_size, decode_fec) -> int
        lib.opus_decode.argtypes = [
            ctypes.c_void_p, ctypes.c_char_p, ctypes.c_int,
            ctypes.POINTER(ctypes.c_short), ctypes.c_int, ctypes.c_int
        ]
        lib.opus_decode.restype = ctypes.c_int

        # opus_decoder_destroy(decoder)
        lib.opus_decoder_destroy.argtypes = [ctypes.c_void_p]
        lib.opus_decoder_destroy.restype = None

        error = ctypes.c_int()
        self._decoder = lib.opus_decoder_create(SAMPLE_RATE, CHANNELS, ctypes.byref(error))
        if error.value != 0:
            raise RuntimeError(f"Failed to create Opus decoder: error {error.value}")

        self._pcm_buffer = (ctypes.c_short * (SAMPLES_PER_FRAME * CHANNELS))()
        logger.debug("Opus decoder initialized")

    def decode(self, data: bytes) -> bytes:
        """Decode Opus packet to PCM (16-bit 48kHz stereo)."""
        import ctypes

        if data == SILENCE_FRAME:
            return b'\x00' * (SAMPLES_PER_FRAME * CHANNELS * 2)

        result = self._lib.opus_decode(
            self._decoder,
            data, len(data),
            self._pcm_buffer, SAMPLES_PER_FRAME,
            0  # no FEC
        )

        if result < 0:
            logger.warning("Opus decode error", code=result)
            return b'\x00' * (SAMPLES_PER_FRAME * CHANNELS * 2)

        # result is number of samples per channel decoded
        return bytes(self._pcm_buffer)[:result * CHANNELS * 2]

    def __del__(self):
        if self._decoder and self._lib:
            self._lib.opus_decoder_destroy(self._decoder)


class VoiceReceiver:
    """Receives and decodes audio from a disnake VoiceClient's UDP socket."""

    def __init__(self, voice_client: disnake.VoiceClient,
                 callback: Optional[Callable[[bytes, int], None]] = None):
        self.vc = voice_client
        self.callback = callback
        self._running = False
        self._thread: Optional[threading.Thread] = None
        self._decoders: Dict[int, OpusDecoder] = {}  # ssrc -> decoder
        self._dave_decryptors: Dict[int, object] = {}  # ssrc -> dave.Decryptor
        self._ssrc_to_user: Dict[int, int] = {}  # ssrc -> user_id

    def start(self):
        """Start receiving audio in a background thread."""
        if self._running:
            return

        self._running = True
        self._thread = threading.Thread(target=self._recv_loop, daemon=True)
        self._thread.start()
        logger.info("Voice receiver started")

    def stop(self):
        """Stop receiving audio."""
        self._running = False
        if self._thread:
            self._thread.join(timeout=2)
            self._thread = None
        self._decoders.clear()
        self._dave_decryptors.clear()
        logger.info("Voice receiver stopped")

    def _get_decoder(self, ssrc: int) -> OpusDecoder:
        """Get or create an Opus decoder for a given SSRC."""
        if ssrc not in self._decoders:
            self._decoders[ssrc] = OpusDecoder()
        return self._decoders[ssrc]

    def _get_user_id_for_ssrc(self, ssrc: int) -> int:
        """Look up user ID from SSRC."""
        # Check our own mapping first
        if ssrc in self._ssrc_to_user:
            return self._ssrc_to_user[ssrc]
        # Try disnake's WebSocket SSRC map
        try:
            if hasattr(self.vc, 'ws') and self.vc.ws is not None:
                ssrc_map = getattr(self.vc.ws, 'ssrc_map', {})
                if ssrc in ssrc_map:
                    return ssrc_map[ssrc].get('user_id', 0)
        except Exception:
            pass
        return 0

    def _decrypt_srtp(self, data: bytes) -> Optional[tuple]:
        """Decrypt an SRTP packet. Returns (header, decrypted_audio, ssrc) or None.

        Discord's aead_xchacha20_poly1305_rtpsize mode:
        - AAD = fixed RTP header (12 + CC*4) + extension header (4 bytes) if X bit set
        - Extension DATA is encrypted along with the audio payload
        - Nonce = last 4 bytes of packet, zero-padded to 24 bytes
        - Encrypted = extension data + audio payload + 16-byte MAC
        """
        if len(data) < RTP_HEADER_SIZE + 4:  # header + nonce
            return None

        # Fixed RTP header: 12 bytes + CC*4 bytes of CSRC
        cc = data[0] & 0x0F
        aad_len = RTP_HEADER_SIZE + cc * 4

        # If extension bit (X) is set, the 4-byte extension header
        # (profile + length) is part of the AAD, but extension DATA is encrypted
        has_ext = bool(data[0] & 0x10)
        if has_ext:
            if len(data) < aad_len + 4 + 4:  # need ext header + nonce minimum
                return None
            aad_len += 4  # include extension profile (2) + length (2)

        aad = data[:aad_len]
        ssrc = struct.unpack_from('>I', data, 8)[0]

        # Nonce is last 4 bytes, zero-padded to 24 for XChacha20
        nonce_bytes = data[-4:]
        encrypted = data[aad_len:-4]

        if not encrypted:
            return None

        try:
            box = nacl.secret.Aead(bytes(self.vc.secret_key))
            padded_nonce = nonce_bytes.ljust(nacl.secret.Aead.NONCE_SIZE, b'\0')
            decrypted = box.decrypt(encrypted, aad=bytes(aad), nonce=padded_nonce)
            plaintext = bytes(decrypted)

            # Strip encrypted extension data from the decrypted payload
            if has_ext:
                ext_data_len = struct.unpack_from('>H', data, aad_len - 2)[0] * 4
                if len(plaintext) > ext_data_len:
                    plaintext = plaintext[ext_data_len:]
                else:
                    return None

            return (aad, plaintext, ssrc)
        except Exception as e:
            if not hasattr(self, '_decrypt_err_count'):
                self._decrypt_err_count = 0
            self._decrypt_err_count += 1
            if self._decrypt_err_count <= 5:
                logger.warning("SRTP decrypt failed",
                               error=str(e),
                               packet_len=len(data),
                               aad_len=aad_len,
                               has_ext=has_ext,
                               first_byte=hex(data[0]))
            return None

    def _decrypt_dave(self, ssrc: int, audio_data: bytes) -> Optional[bytes]:
        """Decrypt DAVE-encrypted audio frame. Returns decrypted data or None."""
        if not has_dave:
            return audio_data  # No DAVE library, assume passthrough

        # Check if DAVE is active
        dave_state = getattr(self.vc, 'dave', None)
        if dave_state is None:
            return audio_data  # No DAVE, passthrough

        # Get or create decryptor for this SSRC
        if ssrc not in self._dave_decryptors:
            decryptor = _dave.Decryptor()
            has_group = False
            try:
                has_group = dave_state._session.has_established_group()
            except Exception:
                pass

            if has_group:
                # disnake doesn't map SSRC→user_id (no SPEAKING handler).
                # Get ratchets for all other recognized users and try them.
                self_id = dave_state._self_id
                other_users = [u for u in dave_state._recognized_users if u != self_id]
                logger.info("Setting up DAVE decryptor",
                            ssrc=ssrc, other_users=other_users, has_group=has_group)

                for uid in other_users:
                    try:
                        ratchet = dave_state._session.get_key_ratchet(str(uid))
                        if ratchet:
                            decryptor.transition_to_key_ratchet(ratchet)
                            self._ssrc_to_user[ssrc] = uid
                            logger.info("DAVE ratchet set for user", user_id=uid, ssrc=ssrc)
                            break
                    except Exception as e:
                        logger.debug("Could not get DAVE ratchet", user_id=uid, error=str(e))
            else:
                logger.warning("DAVE: MLS group not established yet", ssrc=ssrc)

            self._dave_decryptors[ssrc] = decryptor

        decryptor = self._dave_decryptors[ssrc]
        try:
            result = decryptor.decrypt(_dave.MediaType.audio, audio_data)
            if result is not None:
                if not hasattr(self, '_dave_ok_count'):
                    self._dave_ok_count = 0
                self._dave_ok_count += 1
                if self._dave_ok_count <= 3:
                    logger.info("DAVE decrypt OK", ssrc=ssrc, in_len=len(audio_data), out_len=len(result))
                return result
            else:
                if not hasattr(self, '_dave_none_count'):
                    self._dave_none_count = 0
                self._dave_none_count += 1
                if self._dave_none_count <= 5:
                    logger.warning("DAVE decrypt returned None", ssrc=ssrc, in_len=len(audio_data))
                return None
        except Exception as e:
            logger.warning("DAVE decrypt exception", ssrc=ssrc, error=str(e))
            return None

    def update_dave_ratchets(self):
        """Update DAVE decryptors with new key ratchets after a transition."""
        if not has_dave:
            return

        dave_state = getattr(self.vc, 'dave', None)
        if dave_state is None or not dave_state._session.has_established_group():
            return

        for ssrc, decryptor in self._dave_decryptors.items():
            user_id = self._get_user_id_for_ssrc(ssrc)
            if user_id:
                try:
                    ratchet = dave_state._session.get_key_ratchet(str(user_id))
                    if ratchet:
                        decryptor.transition_to_key_ratchet(ratchet)
                except Exception:
                    pass

    # Debug: save raw 48kHz stereo PCM from Opus decoder
    _debug_raw_pcm = bytearray()
    _debug_raw_saved = False

    def _recv_loop(self):
        """Main receive loop running in a background thread."""
        logger.info("Voice receive loop started",
                    socket_exists=self.vc.socket is not None,
                    socket_fd=self.vc.socket.fileno() if self.vc.socket else -1,
                    ssrc=self.vc.ssrc,
                    endpoint=f"{self.vc.endpoint_ip}:{self.vc.voice_port}" if hasattr(self.vc, 'endpoint_ip') else "unknown",
                    callback_set=self.callback is not None,
                    secret_key_set=hasattr(self.vc, 'secret_key') and self.vc.secret_key is not None,
                    secret_key_len=len(self.vc.secret_key) if hasattr(self.vc, 'secret_key') and self.vc.secret_key else 0,
                    has_nacl=has_nacl,
                    has_dave=has_dave,
                    dave_active=getattr(self.vc, 'dave', None) is not None)

        import time as _time
        packet_count = 0
        decrypt_fail_count = 0
        dave_fail_count = 0
        last_status_time = _time.monotonic()

        while self._running:
            try:
                if not self.vc.socket or self.vc.socket.fileno() == -1:
                    logger.warning("Voice socket closed, stopping receive loop")
                    break

                try:
                    data = self.vc.socket.recv(4096)
                except (BlockingIOError, OSError):
                    _time.sleep(0.005)
                    continue

                if not data or len(data) < RTP_HEADER_SIZE:
                    continue

                packet_count += 1

                # Log status periodically
                now = _time.monotonic()
                if now - last_status_time > 5.0:
                    logger.info("Voice receive status",
                                packets_received=packet_count,
                                decrypt_failures=decrypt_fail_count,
                                dave_failures=dave_fail_count)
                    last_status_time = now

                # Skip non-RTP packets (version must be 2)
                if (data[0] & 0xC0) != 0x80:
                    continue

                # Log first few packets for debugging
                if packet_count <= 5:
                    pt = data[1] & 0x7F
                    ssrc_val = struct.unpack_from('>I', data, 8)[0]
                    logger.info("Received UDP packet",
                                length=len(data),
                                payload_type=pt,
                                ssrc=ssrc_val,
                                our_ssrc=self.vc.ssrc,
                                first_byte=hex(data[0]),
                                has_extension=bool(data[0] & 0x10),
                                csrc_count=data[0] & 0x0F,
                                hex_first_20=data[:20].hex(),
                                hex_last_8=data[-8:].hex(),
                                secret_key_set=self.vc.secret_key is not None,
                                secret_key_len=len(self.vc.secret_key) if hasattr(self.vc, 'secret_key') and self.vc.secret_key else 0)

                # Skip RTCP packets (payload type 72-76)
                pt = data[1] & 0x7F
                if pt >= 72 and pt <= 76:
                    continue

                # Decrypt SRTP
                result = self._decrypt_srtp(data)
                if result is None:
                    decrypt_fail_count += 1
                    if decrypt_fail_count <= 3:
                        logger.debug("SRTP decrypt failed",
                                    packet_len=len(data),
                                    pt=data[1] & 0x7F)
                    continue

                header, audio_data, ssrc = result

                # Skip our own audio
                if ssrc == self.vc.ssrc:
                    continue

                if not hasattr(self, '_decrypt_ok_count'):
                    self._decrypt_ok_count = 0
                self._decrypt_ok_count += 1
                if self._decrypt_ok_count <= 5:
                    logger.info("SRTP decrypt SUCCESS",
                                ssrc=ssrc,
                                audio_len=len(audio_data),
                                user_id=self._get_user_id_for_ssrc(ssrc),
                                total_ok=self._decrypt_ok_count)

                # Decrypt DAVE if active
                decrypted = self._decrypt_dave(ssrc, audio_data)
                if decrypted is None:
                    dave_fail_count += 1
                    if dave_fail_count <= 3:
                        logger.debug("DAVE decrypt failed", ssrc=ssrc)
                    continue

                # Decode Opus to PCM
                try:
                    decoder = self._get_decoder(ssrc)
                    pcm_data = decoder.decode(decrypted)
                    if self._decrypt_ok_count <= 3:
                        logger.info("Opus decode OK", ssrc=ssrc, pcm_len=len(pcm_data))
                except Exception as e:
                    logger.warning("Opus decode failed", ssrc=ssrc, error=str(e), error_type=type(e).__name__)
                    continue

                # Debug: save raw 48kHz stereo PCM to WAV
                if not VoiceReceiver._debug_raw_saved:
                    VoiceReceiver._debug_raw_pcm.extend(pcm_data)
                    # Save after ~2 seconds (48000 * 2ch * 2bytes * 2sec = 384000)
                    if len(VoiceReceiver._debug_raw_pcm) > 384000:
                        import wave
                        wav_path = "/Users/matthewpricephd/coding/discord-ai-cohost/debug_raw_48k.wav"
                        with wave.open(wav_path, 'wb') as wf:
                            wf.setnchannels(2)
                            wf.setsampwidth(2)
                            wf.setframerate(48000)
                            wf.writeframes(bytes(VoiceReceiver._debug_raw_pcm))
                        logger.info("Saved raw 48kHz stereo debug WAV", path=wav_path, size=len(VoiceReceiver._debug_raw_pcm))
                        VoiceReceiver._debug_raw_saved = True

                # Deliver to callback
                if self.callback and pcm_data:
                    user_id = self._get_user_id_for_ssrc(ssrc)
                    try:
                        result = self.callback(pcm_data, user_id)
                        # If callback is async, schedule it on the event loop
                        if asyncio.iscoroutine(result):
                            loop = self.vc.loop
                            asyncio.run_coroutine_threadsafe(result, loop)
                    except Exception as e:
                        logger.error("Audio callback error", error=str(e))

            except Exception as e:
                if self._running:
                    logger.error("Voice receive error", error=str(e))
                    _time.sleep(0.1)

        logger.info("Voice receive loop ended", total_packets=packet_count)
