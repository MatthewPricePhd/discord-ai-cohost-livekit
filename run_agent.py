"""Entry point for the LiveKit Agent Worker process."""
from dotenv import load_dotenv
load_dotenv()

from livekit import agents
from src.agent.worker import server

if __name__ == "__main__":
    agents.cli.run_app(server)
