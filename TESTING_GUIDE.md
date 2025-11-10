# Discord AI Co-Host Bot - Comprehensive Testing Guide

## Overview
This testing guide provides detailed step-by-step test cases to systematically validate all features of the Discord AI Co-Host Bot with the new **Split-Stack Architecture**. Each test case includes specific inputs, expected outputs, and success criteria for the updated system.

## Pre-Testing Setup

### Prerequisites
1. **Docker Environment**: Ensure Docker and docker-compose are running
2. **Browser Access**: Open `http://localhost:8000` in your web browser
3. **Discord Account**: Have a Discord account with access to voice channels (optional for core testing)
4. **Test Files**: Prepare test documents (PDF, DOCX, TXT, MD files under 50MB)

### Initial Verification
1. Verify containers are running: `docker ps` should show both containers as "healthy"
2. Verify web interface loads without errors
3. Check browser console for JavaScript errors (F12 → Console tab)

---

## Test Suite 1: New Interface Layout and Split-Stack Architecture

### Test 1.1: Dashboard Layout Verification
**Objective**: Verify new 3-section layout loads correctly with split-stack controls

**Steps**:
1. Navigate to `http://localhost:8000`
2. Wait for page to fully load
3. Observe layout structure

**Expected Results**:
- **Column 1 (Left)**: 
  - **Control Panel** section with:
    - Discord Voice Channel selector
    - AI Mode (Split-Stack) with 3 mode buttons
    - Force AI Response button
    - Ask ChatGPT section
  - **Configuration** section with:
    - Model Choices (Text Processing, STT, TTS, Voice)
    - Session Spend widget
- **Column 2 (Middle)**:
  - ChatGPT Response (top)
  - Documents section (middle)
  - Context Summary (bottom)
- **Column 3 (Right)**: 
  - Live Conversation (full height)
- Top navigation shows status indicators

**Success Criteria**: ✅ New 3-section layout displays correctly with all split-stack controls

---

### Test 1.2: Split-Stack Mode Selection
**Objective**: Test the new 3-mode split-stack architecture

**Steps**:
1. Locate "AI Mode (Split-Stack)" section in Control Panel
2. Observe the 3 mode buttons:
   - Passive Listening (blue icon)
   - Speech-to-Speech (green icon)  
   - Ask ChatGPT (purple icon)
3. Click each mode button and observe changes

**Expected Results**:
- **Passive Listening**:
  - Button highlighted with active styling
  - Description: "Transcription-only mode, minimal cost"
  - Current mode indicator shows "Passive Listening"
  - Status: "Transcription-only mode active"
- **Speech-to-Speech**:
  - Button highlighted when selected
  - Description: "Full voice interaction with responses"  
  - Current mode indicator updates
  - Status: "STT + TTS pipeline active"
- **Ask ChatGPT**:
  - Button highlighted when selected
  - Description: "Text-only Q&A, fastest response"
  - Current mode indicator shows "Ask ChatGPT"
  - Status: "Text-only mode active"

**Success Criteria**: ✅ All 3 split-stack modes selectable with proper UI feedback

---

### Test 1.3: Model Choices Configuration
**Objective**: Test new model selection dropdowns in Configuration section

**Steps**:
1. Locate "Model Choices" in Configuration section
2. Test each dropdown:
   - Text Processing
   - Speech-to-Text
   - Text-to-Speech
   - TTS Voice
3. Change selections and observe

**Expected Results**:
- **Text Processing**: Shows GPT-5 Mini (default), GPT-5, GPT-4o Legacy options
- **Speech-to-Text**: Shows Whisper-1 (default), GPT-4o Mini Transcribe options
- **Text-to-Speech**: Shows TTS-1 (default), TTS-1 HD options  
- **TTS Voice**: Shows Alloy (default), Echo, Fable, Onyx, Nova, Shimmer options
- Selections persist when changed
- Success message appears when configuration updated

**Success Criteria**: ✅ All model selections functional with proper options

---

## Test Suite 2: Split-Stack Operational Modes

### Test 2.1: Passive Listening Mode
**Objective**: Test STT-only transcription mode for cost efficiency

**Steps**:
1. Select "Passive Listening" mode
2. Observe mode status indicator
3. Check cost tracking (if available)

**Expected Results**:
- Mode indicator shows "Passive Listening" 
- Status: "Transcription-only mode active"
- STT cost tracking begins if audio is processed
- No TTS or text processing costs incurred
- Efficient resource usage

**Success Criteria**: ✅ Passive mode operates with STT-only functionality

---

### Test 2.2: Speech-to-Speech Mode  
**Objective**: Test full STT + reasoning + TTS pipeline

**Steps**:
1. Select "Speech-to-Speech" mode
2. Observe mode status changes
3. Use Force AI Response button to test pipeline
4. Check cost tracking for all components

**Expected Results**:
- Mode indicator shows "Speech-to-Speech"
- Status: "STT + TTS pipeline active" 
- Force AI Response generates audio response
- Cost tracking shows STT, TTS, and text processing costs
- Full voice interaction capability enabled

**Success Criteria**: ✅ Speech-to-Speech mode enables complete voice pipeline

---

### Test 2.3: Ask ChatGPT Mode
**Objective**: Test text-only Q&A mode for fastest response

**Steps**:
1. Select "Ask ChatGPT" mode
2. Enter question in Ask ChatGPT text area
3. Click "Ask ChatGPT" button
4. Observe response and cost tracking

**Expected Results**:
- Mode indicator shows "Ask ChatGPT"
- Status: "Text-only mode active"
- Text responses appear in ChatGPT Response section
- Only text processing costs tracked (no STT/TTS)
- Fastest response time of all modes

**Success Criteria**: ✅ Ask ChatGPT mode provides text-only responses efficiently

---

## Test Suite 3: Enhanced Cost Tracking System

### Test 3.1: Session Spend Widget Basic Functions
**Objective**: Test new cost tracking for split-stack architecture

**Steps**:
1. Locate Session Spend widget in Configuration section
2. Click "Start" button to begin session tracking
3. Perform various actions (ChatGPT queries, mode switches)
4. Click "Stop & Calculate" button
5. Review cost breakdown

**Expected Results**:
- **During Session**: 
  - Start button becomes disabled
  - Stop button becomes enabled  
  - Status shows "Session running for: X seconds"
- **After Stop**:
  - Session summary displays with detailed breakdown
  - **STT (Speech-to-Text)**: Cost and minutes used
  - **TTS (Text-to-Speech)**: Cost and minutes used
  - **Text Processing**: Cost and token count
  - **Total Cost**: Sum of all components
  - Usage metrics: STT minutes, TTS minutes, total tokens, API requests

**Success Criteria**: ✅ Cost tracking captures all split-stack components accurately

---

### Test 3.2: GPT-5 Model Cost Efficiency
**Objective**: Verify GPT-5 models provide cost savings over GPT-4o

**Steps**:
1. Start session tracking
2. Make several ChatGPT queries using default GPT-5-mini
3. Note cost per query
4. Compare with expected GPT-4o costs (if available)
5. Stop session and review total

**Expected Results**:
- GPT-5-mini rates: $0.30/$0.60 per 1K input/output tokens (lower than GPT-4o)
- Text processing costs significantly reduced
- Total session cost reflects GPT-5 efficiency
- Cost breakdown shows model used and pricing

**Success Criteria**: ✅ GPT-5 models demonstrate cost efficiency vs GPT-4o

---

### Test 3.3: Multi-Component Cost Breakdown
**Objective**: Test cost tracking across all split-stack components

**Steps**:
1. Start session in Speech-to-Speech mode
2. Generate text responses (text processing cost)
3. Simulate audio transcription (STT cost)
4. Generate TTS responses (TTS cost)
5. Stop session and verify breakdown

**Expected Results**:
- **STT Cost**: $0.006 per minute rate applied correctly
- **TTS Cost**: $0.015 per minute rate applied correctly
- **Token Cost**: GPT-5-mini rates applied correctly
- **Total Cost**: Mathematical sum of all components
- **Usage Metrics**: Accurate counts for minutes and tokens
- All costs displayed to 6 decimal places for precision

**Success Criteria**: ✅ All cost components tracked accurately with proper rates

---

## Test Suite 4: ChatGPT Integration with GPT-5

### Test 4.1: GPT-5-mini Text Completion
**Objective**: Test GPT-5-mini integration for cost-efficient responses

**Test Input**:
```
What is the capital of France?
```

**Steps**:
1. Ensure "GPT-5 Mini (Cost Efficient)" is selected in Model Choices
2. Enter test input in Ask ChatGPT area
3. Click "Ask ChatGPT" button
4. Monitor cost tracking

**Expected Results**:
- Response mentions "Paris" as capital of France
- Processing time: 2-8 seconds (improved efficiency)
- Cost tracking shows GPT-5-mini rates ($0.30/$0.60 per 1K tokens)
- Token usage reasonable for query complexity
- Response quality comparable to GPT-4o

**Success Criteria**: ✅ GPT-5-mini provides accurate responses at reduced cost

---

### Test 4.2: Model Switching Test
**Objective**: Test switching between different text processing models

**Steps**:
1. Ask question using GPT-5-mini (default)
2. Change to "GPT-5 (Higher Accuracy)" in Model Choices  
3. Ask similar complexity question
4. Compare costs and response quality
5. Switch to "GPT-4o (Legacy)" and repeat

**Expected Results**:
- **GPT-5-mini**: Lowest cost, good quality responses
- **GPT-5**: Higher cost than mini, potentially better accuracy
- **GPT-4o Legacy**: Highest cost, familiar GPT-4o quality
- Model selection persists between queries
- Cost breakdown reflects different model rates
- All models provide suitable responses

**Success Criteria**: ✅ Model switching works with appropriate cost differences

---

## Test Suite 5: Documents Integration (New Location)

### Test 5.1: Documents Section Location  
**Objective**: Verify Documents section moved to Column 2 above Context Summary

**Steps**:
1. Locate Documents section in Column 2 (middle)
2. Verify it's positioned between ChatGPT Response and Context Summary
3. Check "Send to Context" button placement

**Expected Results**:
- Documents section in Column 2, middle position
- Upload area and document list clearly visible
- "Send to Context" button in section header for easy access
- Visual grouping with Context Summary below makes logical sense

**Success Criteria**: ✅ Documents section properly positioned near Context Summary

---

### Test 5.2: Document Upload and Integration
**Objective**: Test document upload workflow in new location

**Steps**:
1. Upload test document in Documents section
2. Click "Send to Context" button  
3. Observe Context Summary update immediately below
4. Test multiple document workflow

**Expected Results**:
- Document upload functions identical to previous version
- "Send to Context" immediately updates Context Summary below
- Workflow feels intuitive with related sections adjacent
- Multiple documents handled correctly
- File list displays properly in middle column

**Success Criteria**: ✅ Document workflow improved by new positioning

---

## Test Suite 6: Context Summary and Export

### Test 6.1: Context Summary Generation
**Objective**: Test context summary with GPT-5 models

**Steps**:
1. Add ChatGPT responses to context  
2. Upload and add documents to context
3. Click "Generate" button in Context Summary
4. Review generated summary quality

**Expected Results**:
- Summary generation uses GPT-5-mini for cost efficiency
- Quality maintains high standard despite cost optimization
- Processing time: 5-15 seconds
- Summary integrates multiple information sources effectively
- Cost tracking reflects GPT-5 usage

**Success Criteria**: ✅ Context summary quality maintained with GPT-5 efficiency

---

### Test 6.2: Export Functionality
**Objective**: Test context and transcript export features

**Steps**:
1. Build comprehensive context summary
2. Generate some conversation activity
3. Test both export buttons:
   - Export context summary
   - Export live conversation transcript
4. Check created files

**Expected Results**:
- Export buttons disabled during active processing
- Export buttons enabled in passive mode
- Files created in `/exports` directory
- **Context Export**: `context_summary_YYYYMMDD_HHMMSS.md`
- **Transcript Export**: `conversation_transcript_YYYYMMDD_HHMMSS.md` 
- Files contain properly formatted markdown content
- Toast notifications confirm successful exports

**Success Criteria**: ✅ Export functionality works correctly with proper state management

---

## Test Suite 7: Voice Channel and Force AI Response

### Test 7.1: Force AI Response with Split-Stack Modes
**Objective**: Test Force AI Response button behavior in different modes

**Steps**:
1. Test Force AI Response in each split-stack mode:
   - Passive Listening mode
   - Speech-to-Speech mode
   - Ask ChatGPT mode
2. Observe different behaviors

**Expected Results**:
- **Passive Mode**: Generates text response only
- **Speech-to-Speech Mode**: Generates text + audio response (TTS)
- **Ask ChatGPT Mode**: Generates optimized text response
- Cost tracking reflects mode-appropriate services used
- Response time varies by mode complexity

**Success Criteria**: ✅ Force AI Response adapts behavior based on active split-stack mode

---

### Test 7.2: Voice Channel Integration
**Objective**: Test voice channel controls (mock test acceptable)

**Steps**:
1. Click Discord Voice Channel dropdown
2. Try Join/Leave buttons
3. Observe error handling without Discord bot token

**Expected Results**:
- Dropdown shows "Select a channel..." initially
- May show "Discord bot not ready" errors (expected without token)
- Join/Leave buttons respond appropriately
- Error messages are user-friendly
- No application crashes from Discord connection failures

**Success Criteria**: ✅ Voice channel interface functional (errors acceptable without token)

---

## Test Suite 8: Error Handling and Edge Cases

### Test 8.1: GPT-5 Model Error Handling
**Objective**: Test error handling for GPT-5 model issues

**Steps**:
1. Simulate network issues during GPT-5 requests
2. Test with invalid API keys (if configurable)
3. Test with rate limiting scenarios

**Expected Results**:
- Appropriate error messages for different failure types
- Graceful fallback behavior when possible
- No application crashes or undefined states
- User-friendly error explanations
- Recovery possible when issues resolved

**Success Criteria**: ✅ GPT-5 integration handles errors gracefully

---

### Test 8.2: Split-Stack Mode Switching Errors
**Objective**: Test error handling during mode transitions

**Steps**:
1. Switch between modes rapidly
2. Switch modes during active processing
3. Test mode switching with network issues

**Expected Results**:
- Mode switches complete successfully
- No stuck states between modes
- Processing interruptions handled cleanly
- Clear status indicators during transitions
- Mode state persists correctly

**Success Criteria**: ✅ Mode switching robust against error conditions

---

## Test Suite 9: End-to-End Split-Stack Workflows

### Test 9.1: Cost-Optimized Podcast Preparation
**Objective**: Test complete workflow optimized for cost efficiency

**Scenario**: "Preparing AI co-host for podcast while minimizing costs"

**Steps**:
1. **Start in Passive Listening mode** for cost-efficient transcription
2. **Upload relevant documents** for podcast topic
3. **Use Ask ChatGPT mode** for preparation questions
4. **Send documents and responses to context**
5. **Generate context summary** using GPT-5-mini  
6. **Switch to Speech-to-Speech mode** when ready for voice interaction
7. **Track costs throughout** using Session Spend widget

**Expected Results**:
- **Passive Mode**: Minimal costs during preparation phase
- **Ask ChatGPT Mode**: Efficient text-only Q&A
- **Document Integration**: Context building without unnecessary processing
- **GPT-5 Usage**: Reduced costs vs GPT-4o baseline  
- **Speech-to-Speech Mode**: Full capability when needed
- **Cost Tracking**: Clear breakdown of all components
- **Final State**: AI prepared with comprehensive, cost-effective context

**Success Criteria**: ✅ Complete workflow demonstrates split-stack cost optimization

---

### Test 9.2: Real-World Performance Comparison
**Objective**: Compare new split-stack architecture vs previous single-model approach

**Steps**:
1. **Document Previous Approach**: Note hypothetical GPT-4o costs for similar workflow
2. **Execute Split-Stack Workflow**: Complete Test 9.1 with cost tracking
3. **Compare Results**: Analyze cost savings and functionality differences
4. **Test Performance**: Measure response times and quality

**Expected Results**:
- **Cost Savings**: 40-60% reduction vs GPT-4o across all operations
- **Response Time**: Similar or improved due to model efficiency
- **Quality**: Maintained high quality despite cost optimization  
- **Functionality**: Enhanced with split-stack operational flexibility
- **Resource Usage**: More efficient resource allocation per mode

**Success Criteria**: ✅ Split-stack architecture demonstrates clear improvements

---

## Test Suite 10: Advanced Features and Edge Cases

### Test 10.1: Session Cost Accuracy Verification
**Objective**: Verify cost calculations match expected OpenAI pricing

**Reference Pricing** (GPT-5 models):
- GPT-5-mini: $0.30/$0.60 per 1K input/output tokens  
- STT (Whisper-1): $0.006 per minute
- TTS (TTS-1): $0.015 per minute

**Steps**:
1. Start session with known token/minute usage
2. Execute specific actions with measurable costs
3. Calculate expected costs manually
4. Compare with Session Spend widget results

**Expected Results**:
- Token counts reasonable for input/output sizes
- Manual calculations match widget calculations
- Precision maintained to 6 decimal places
- All cost components sum correctly
- Rates match current OpenAI pricing

**Success Criteria**: ✅ Cost calculations mathematically accurate

---

### Test 10.2: Model Configuration Persistence
**Objective**: Test model choice persistence across sessions

**Steps**:
1. Change model selections in Model Choices
2. Refresh browser page
3. Check if selections persist
4. Restart container and retest

**Expected Results**:
- Model selections persist across page refreshes
- Default selections restore after container restart
- Configuration changes apply immediately  
- No loss of settings during normal usage

**Success Criteria**: ✅ Model configuration behaves predictably

---

## Test Suite 11: UI/UX Validation

### Test 11.1: Responsive Layout Testing
**Objective**: Test new layout across different screen sizes

**Steps**:
1. Test on desktop (1920px+)
2. Test on laptop (1366px)  
3. Test on tablet (1024px)
4. Test on mobile (768px-)

**Expected Results**:
- **Desktop**: Full 3-column layout with proper spacing
- **Laptop**: Compressed but functional 3-column layout
- **Tablet**: Possibly stacked columns, all features accessible
- **Mobile**: Single column stack, touch-friendly interactions
- No horizontal scrolling required
- All functionality preserved across sizes

**Success Criteria**: ✅ Layout adapts properly maintaining usability

---

### Test 11.2: Message System Testing
**Objective**: Test inline message systems for all sections

**Steps**:
1. Trigger various actions that generate messages
2. Observe message positioning and timing
3. Check for UI layout shifts

**Expected Results**:
- Messages appear adjacent to section titles
- No UI jumping or layout shifts
- Messages auto-fade after appropriate time
- Different message types (success, error, warning) clearly distinguished
- Messages don't interfere with functionality

**Success Criteria**: ✅ Message system provides clear feedback without UI disruption

---

## Reporting Issues and Feedback

### Issue Report Format
When reporting issues, please include:

1. **Test Case**: Which test case failed
2. **Steps Taken**: Exact steps you followed  
3. **Expected Result**: What should have happened
4. **Actual Result**: What actually happened
5. **Split-Stack Mode**: Which operational mode was active
6. **Model Configuration**: Which models were selected
7. **Screenshots**: If applicable
8. **Browser Console Errors**: Check F12 → Console for errors
9. **Environment**: Browser type/version, OS

### Success Metrics
- **Critical**: Split-stack modes, cost tracking, GPT-5 integration
- **Important**: UI layout, model switching, document workflow  
- **Minor**: Visual styling, minor usability issues

### Testing Completion Checklist

#### **Split-Stack Architecture (Critical)**
- [ ] Test Suite 1: New Interface Layout ✅
- [ ] Test Suite 2: Split-Stack Operational Modes ✅
- [ ] Test Suite 3: Enhanced Cost Tracking System ✅

#### **Core Features (Critical)**
- [ ] Test Suite 4: ChatGPT Integration with GPT-5 ✅
- [ ] Test Suite 5: Documents Integration (New Location) ✅
- [ ] Test Suite 6: Context Summary and Export ✅

#### **System Features (Important)**  
- [ ] Test Suite 7: Voice Channel and Force AI Response ✅
- [ ] Test Suite 8: Error Handling and Edge Cases ✅

#### **Workflow Testing (Critical)**
- [ ] Test Suite 9: End-to-End Split-Stack Workflows ✅

#### **Advanced Features (Important)**
- [ ] Test Suite 10: Advanced Features and Edge Cases ✅
- [ ] Test Suite 11: UI/UX Validation ✅

---

## Quick Reference

### Key URLs
- Dashboard: `http://localhost:8000/`
- Logs: `http://localhost:8000/logs`

### Split-Stack Modes
- **Passive Listening**: STT transcription only, minimal cost
- **Speech-to-Speech**: Full STT + reasoning + TTS pipeline  
- **Ask ChatGPT**: Text-only Q&A, fastest response

### Model Options
- **Text Processing**: GPT-5-mini (default), GPT-5, GPT-4o-legacy
- **Speech-to-Text**: Whisper-1 (default), GPT-4o-mini-transcribe
- **Text-to-Speech**: TTS-1 (default), TTS-1-HD
- **TTS Voice**: Alloy, Echo, Fable, Onyx, Nova, Shimmer

### Expected Processing Times
- **GPT-5-mini queries**: 2-8 seconds (improved)
- **Document uploads**: 1-5 seconds
- **Context generation**: 5-15 seconds  
- **Mode switching**: < 2 seconds

### Cost Optimization  
- **GPT-5-mini**: ~60% cost reduction vs GPT-4o
- **STT**: $0.006/minute (Whisper-1)
- **TTS**: $0.015/minute (TTS-1)
- **Split-Stack**: Use appropriate mode for task

### File Support
- **Supported**: PDF, DOCX, TXT, MD
- **Size Limit**: 50MB per file  
- **Multiple uploads**: Supported

---

This comprehensive testing guide covers all new split-stack architecture features, cost optimization capabilities, and the reorganized UI layout. The focus is on validating the cost efficiency improvements and operational mode flexibility that makes this system significantly more practical for real-world podcast co-hosting scenarios.