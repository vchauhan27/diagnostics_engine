Reading failure log from D:\diagnostics_engine\indexer\data\sample.log...
Successfully read sample.log.

I'll help you diagnose the failure for TC-CAM-0142. Let me first retrieve the test case details and then start the diagnosis process.

Now I'll start the diagnosis to gather evidence about this failure.

"NullPointerException" AND "SemMultiFrameFusionEngine.allocateBuffer" AND "NightModePipeline.init" AND "com.sec.android.app.camera" AND "Galaxy S24 Ultra" AND "S928BXXU3CXH2"

[Tool Update] Fetching test details for TC-CAM-0142...

[Tool Update] Searching historical failures related to com.sec.android.app.camera...

[Tool Update] Searching code changes related to com.sec.android.app.camera...

"NullPointerException" AND "SemMultiFrameFusionEngine.allocateBuffer" AND "NightModePipeline" AND "com.sec.android.app.camera" AND "Galaxy S24" AND "S928BXXU3CXH2"

[Tool Update] Searching code changes related to com.sec.android.app.camera...

"NullPointerException" "SemMultiFrameFusionEngine.allocateBuffer" "NightModePipeline.init" "ExynosCameraHAL3.setParameters" "com.sec.android.app.camera" "Galaxy S24 Ultra" "S928BXXU3CXH2" "NightMode" "camera HAL" "buffer allocation"

[Tool Update] Searching code changes related to com.sec.android.app.camera...

Evidence gathered:
{'test_details': {'found': True, 'test_case': {'test_case_id': 'TC-CAM-0142', 'project_id': 1, 'project_name': 'Galaxy S24 Ultra', 'feature_id': 'FEAT-CAM-001', 'title': 'Verify Camera Captures Image In Night Mode', 'test_name': 'Verify_Camera_Captures_Image_In_NightMode', 'description': 'Validates that the camera app can successfully capture a photo when Night Mode is enabled on the Galaxy S24 Ultra.', 'preconditions': 'Device must be unlocked. Camera app must be installed (v14.0.02.30+). Night mode toggle must be available.', 'test_steps': '1. Launch Camera app\r\n2. Switch to Photo mode\r\n3. Enable Night Mode via the toggle\r\n4. Point camera at a low-light scene\r\n5. Tap the shutter button\r\n6. Verify image is saved to gallery', 'expected_result': 'Image is captured and saved within 5 seconds. No crash or ANR occurs. Night mode processing completes successfully.', 'priority': 'P1', 'severity': 'High', 'status': 'Failed', 'version': 'S928BXXU3CXH2', 'source': 'Automated-Appium', 'created_at': '2026-09-26T11:36:05.571852', 'updated_at': '2026-09-26T11:36:05.571852'}}, 'historical_failures': [{'content': 'Title: Verify Camera Captures Image In Night Mode\nType: test_execution\nComponent: test_case\nStatus: FAILED\nEnvironment: Staging - Lab 1\nContent: Validates that the camera app can successfully capture a photo when Night Mode is enabled on the Galaxy S24 Ultra. Notes: Test failed. App crashed when Night Mode was enabled.\n', 'metadata': {'source': 'test_execution_EXEC-1001', 'distance': 0.3772648572921753}}, {'content': 'Title: Verify Camera Captures Image In Night Mode\nType: test_execution\nComponent: test_case\nStatus: FAILED\nEnvironment: Staging - Lab 2\nContent: Validates that the camera app can successfully capture a photo when Night Mode is enabled on the Galaxy S24 Ultra. Notes: Image captured was extremely blurry. Does not meet quality thresholds.\n', 'metadata': {'source': 'test_execution_EXEC-1002', 'distance': 0.4004343390723658}}, {'content': 'Title: Camera App crashes on launch in Night Mode\nType: defect\nComponent: Camera\nStatus: Open\nEnvironment: Galaxy S24 Ultra - One UI 6.1\nContent: When the user launches the camera app and immediately switches to Night Mode, the app crashes and returns to the home screen.\n', 'metadata': {'source': 'defect_DEF-001', 'distance': 0.43275184240914866}}, {'content': 'Title: Blurry images in Night Mode\nType: defect\nComponent: Camera\nStatus: Resolved\nEnvironment: Galaxy S24 Ultra - One UI 6.1\nContent: Photos taken in Night Mode are occasionally blurry when the device is slightly moving. OIS does not seem to compensate correctly.\n', 'metadata': {'source': 'defect_DEF-002', 'distance': 0.5327664613723755}}, {'content': 'Title: System crash when draining battery below 5%\nType: defect\nComponent: System\nStatus: Open\nEnvironment: Galaxy S23 - One UI 6.0\nContent: Device abruptly restarts when battery reaches 5% instead of showing low battery warning.\n', 'metadata': {'source': 'defect_DEF-003', 'distance': 0.5783343315124512}}], 'code_changes': []}

Based on the evidence gathered, I can now provide a comprehensive diagnosis for TC-CAM-0142.

## Diagnosis Summary

**Root Cause**: A `NullPointerException` occurs when the `SemMultiFrameFusionEngine` is null during Night Mode initialization. This prevents the camera app from properly initializing the Night Mode pipeline, causing the app to crash and fall back to STANDARD mode instead of capturing in NIGHT mode.

**Evidence**:
- The stack trace clearly shows the NPE in `NightModePipeline.init()` at line 87
- Historical failures show similar crashes in other environments
- Related open defect DEF-001: "Camera App crashes on launch in Night Mode"
- The captured image has `SceneCaptureType=0` (STANDARD) instead of expected `3` (NIGHT)

**Impact**: The Night Mode feature is completely broken on this build, causing app crashes and incorrect image capture.

Let me submit this diagnosis to create a Jira ticket:

Jira ticket created successfully.
