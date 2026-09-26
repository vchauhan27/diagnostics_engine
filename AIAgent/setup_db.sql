-- =============================================================
-- TMS Database Setup + Seed Data
-- Matches the schema queried by agents.py get_test_details tool
-- =============================================================

-- Create DB (run this separately as superuser if tms_db doesn't exist)
-- CREATE DATABASE tms_db;

-- Connect to tms_db then run the rest:
CREATE EXTENSION IF NOT EXISTS vector;

-- ── projects table ────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS projects (
    project_id   SERIAL PRIMARY KEY,
    project_name VARCHAR(255) NOT NULL,
    description  TEXT,
    created_at   TIMESTAMP DEFAULT NOW()
);

-- ── test_cases table ──────────────────────────────────────────
CREATE TABLE IF NOT EXISTS test_cases (
    test_case_id   VARCHAR(50) PRIMARY KEY,
    project_id     INTEGER REFERENCES projects(project_id),
    feature_id     VARCHAR(50),
    title          VARCHAR(500) NOT NULL,
    test_name      VARCHAR(500),
    description    TEXT,
    preconditions  TEXT,
    test_steps     TEXT,
    expected_result TEXT,
    priority       VARCHAR(20),
    severity       VARCHAR(20),
    status         VARCHAR(50),
    version        VARCHAR(50),
    source         VARCHAR(100),
    created_at     TIMESTAMP DEFAULT NOW(),
    updated_at     TIMESTAMP DEFAULT NOW()
);

-- ── Seed: Projects ────────────────────────────────────────────
INSERT INTO projects (project_id, project_name, description) VALUES
(1, 'Galaxy S24 Ultra', 'Samsung Galaxy S24 Ultra camera and system test suite'),
(2, 'Galaxy S23',       'Samsung Galaxy S23 regression and smoke tests'),
(3, 'One UI 6.1',       'One UI 6.1 system integration tests')
ON CONFLICT DO NOTHING;

-- ── Seed: Test Cases ─────────────────────────────────────────
INSERT INTO test_cases VALUES (
    'TC-CAM-0142', 1, 'FEAT-CAM-001',
    'Verify Camera Captures Image In Night Mode',
    'Verify_Camera_Captures_Image_In_NightMode',
    'Validates that the camera app can successfully capture a photo when Night Mode is enabled on the Galaxy S24 Ultra.',
    'Device must be unlocked. Camera app must be installed (v14.0.02.30+). Night mode toggle must be available.',
    '1. Launch Camera app
2. Switch to Photo mode
3. Enable Night Mode via the toggle
4. Point camera at a low-light scene
5. Tap the shutter button
6. Verify image is saved to gallery',
    'Image is captured and saved within 5 seconds. No crash or ANR occurs. Night mode processing completes successfully.',
    'P1', 'High', 'Failed', 'S928BXXU3CXH2', 'Automated-Appium',
    NOW(), NOW()
) ON CONFLICT DO NOTHING;

INSERT INTO test_cases VALUES (
    'TC-CAM-0143', 1, 'FEAT-CAM-001',
    'Verify Camera Night Mode Preview Rendering',
    'Verify_Camera_NightMode_Preview',
    'Validates that the camera preview renders correctly when Night Mode is enabled.',
    'Device unlocked. Camera app installed.',
    '1. Open Camera app
2. Enable Night Mode
3. Observe the live preview',
    'Preview renders without flickering or black frames.',
    'P2', 'Medium', 'Passed', 'S928BXXU3CXH2', 'Automated-Appium',
    NOW(), NOW()
) ON CONFLICT DO NOTHING;

INSERT INTO test_cases VALUES (
    'TC-CAM-0144', 1, 'FEAT-CAM-002',
    'Verify Camera Zoom 10x Does Not Crash',
    'Verify_Camera_Zoom_10x',
    'Verifies that 10x optical zoom works without crashing.',
    'Device unlocked. Rear camera available.',
    '1. Open Camera
2. Pinch-to-zoom to 10x
3. Capture image',
    'Image captured at 10x zoom without crash.',
    'P1', 'High', 'Passed', 'S928BXXU3CXH2', 'Automated-Appium',
    NOW(), NOW()
) ON CONFLICT DO NOTHING;

INSERT INTO test_cases VALUES (
    'TC-CAM-0101', 1, 'FEAT-CAM-003',
    'Verify Camera Cold Start Time Under 1.5s',
    'Verify_Camera_ColdStartTime',
    'Measures cold start time of the camera app.',
    'Device rebooted. Camera not in memory.',
    '1. Reboot device
2. Launch Camera app
3. Measure time to first frame',
    'Camera app opens to preview within 1.5 seconds.',
    'P0', 'Critical', 'Failed', 'S928BXXU3CXH2', 'Automated-Perf',
    NOW(), NOW()
) ON CONFLICT DO NOTHING;

INSERT INTO test_cases VALUES (
    'TC-SYS-0021', 2, 'FEAT-SYS-001',
    'Verify Device Reboot Completes Under 45s',
    'Verify_Device_Reboot_Time',
    'Validates that the device completes a reboot cycle within 45 seconds.',
    'Device is on with screen unlocked.',
    '1. Issue reboot command via ADB
2. Measure time until boot complete intent',
    'Device fully boots within 45 seconds.',
    'P1', 'High', 'Passed', 'S928BXXU3CXH2', 'Automated-ADB',
    NOW(), NOW()
) ON CONFLICT DO NOTHING;

INSERT INTO test_cases VALUES (
    'TC-SYS-0022', 2, 'FEAT-SYS-002',
    'Verify Battery Drain Under Idle 1 Hour',
    'Verify_Battery_Idle_Drain',
    'Validates battery drain is within acceptable limits during 1 hour idle.',
    'Battery at 80%+. No active apps.',
    '1. Record battery level
2. Leave device idle 1 hour
3. Record battery level',
    'Battery drain does not exceed 3% in 1 hour idle.',
    'P2', 'Medium', 'Passed', 'S928BXXU3CXH2', 'Manual',
    NOW(), NOW()
) ON CONFLICT DO NOTHING;

INSERT INTO test_cases VALUES (
    'TC-UI-0055', 3, 'FEAT-UI-001',
    'Verify Home Screen Animation Smoothness',
    'Verify_HomeScreen_Animation',
    'Validates that home screen swipe animations run at 120fps.',
    'Device at home screen.',
    '1. Swipe between home screen pages 10 times
2. Capture frame rate using systrace',
    'Frame rate stays above 90fps throughout all swipes.',
    'P2', 'Medium', 'Failed', 'S928BXXU3CXH2', 'Automated-Systrace',
    NOW(), NOW()
) ON CONFLICT DO NOTHING;
-- ── diagnostic_runs table ─────────────────────────────────────
CREATE TABLE IF NOT EXISTS diagnostic_runs (
    run_id VARCHAR(50) PRIMARY KEY,
    failure_input_json JSONB,
    parsed_failure_json JSONB,
    created_at TIMESTAMP DEFAULT NOW()
);

-- ── Verify ────────────────────────────────────────────────────
SELECT tc.test_case_id, p.project_name, tc.title, tc.status
FROM test_cases tc
JOIN projects p ON tc.project_id = p.project_id
ORDER BY tc.test_case_id;

-- -- idempotency_keys table ------------------------------------
CREATE TABLE IF NOT EXISTS idempotency_keys (
    idempotency_key VARCHAR(64) PRIMARY KEY,
    ticket_json JSONB NOT NULL,
    created_at TIMESTAMP DEFAULT NOW()
);

-- Note: defects and test_executions tables are created by Jira/Adapt sync scripts,
-- but we ensure the pgvector embedding column is added here.
DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM information_schema.tables WHERE table_name = 'defects') THEN
        ALTER TABLE defects ADD COLUMN IF NOT EXISTS embedding vector(1024);
    END IF;
    
    IF EXISTS (SELECT 1 FROM information_schema.tables WHERE table_name = 'test_executions') THEN
        ALTER TABLE test_executions ADD COLUMN IF NOT EXISTS embedding vector(1024);
    END IF;
END $$;

-- ── Seed: Mock Defects & Executions ───────────────────────────
-- (Added for local development and testing)

CREATE TABLE IF NOT EXISTS defects (
    defect_id VARCHAR(50) PRIMARY KEY,
    issue_key VARCHAR(50),
    issue_type VARCHAR(50),
    title VARCHAR(500),
    description TEXT,
    module VARCHAR(100),
    severity VARCHAR(50),
    status VARCHAR(50),
    resolution TEXT,
    environment VARCHAR(100),
    embedding vector(1024)
);

CREATE TABLE IF NOT EXISTS test_executions (
    execution_id VARCHAR(50) PRIMARY KEY,
    test_case_id VARCHAR(50) REFERENCES test_cases(test_case_id),
    status VARCHAR(50),
    device VARCHAR(100),
    environment VARCHAR(100),
    notes TEXT,
    executed_at TIMESTAMP DEFAULT NOW(),
    embedding vector(1024)
);

INSERT INTO defects (defect_id, issue_key, issue_type, title, description, module, severity, status, resolution, environment) VALUES
('DEF-001', 'BUG-101', 'Bug', 'Camera App crashes on launch in Night Mode', 'When the user launches the camera app and immediately switches to Night Mode, the app crashes and returns to the home screen.', 'Camera', 'High', 'Open', NULL, 'Galaxy S24 Ultra - One UI 6.1'),
('DEF-002', 'BUG-102', 'Bug', 'Blurry images in Night Mode', 'Photos taken in Night Mode are occasionally blurry when the device is slightly moving. OIS does not seem to compensate correctly.', 'Camera', 'Medium', 'Resolved', 'Adjusted OIS parameters in the Night Mode HAL module.', 'Galaxy S24 Ultra - One UI 6.1'),
('DEF-003', 'BUG-103', 'Crash', 'System crash when draining battery below 5%', 'Device abruptly restarts when battery reaches 5% instead of showing low battery warning.', 'System', 'Critical', 'Open', NULL, 'Galaxy S23 - One UI 6.0')
ON CONFLICT DO NOTHING;

INSERT INTO test_executions (execution_id, test_case_id, status, device, environment, notes) VALUES
('EXEC-1001', 'TC-CAM-0142', 'FAILED', 'SM-S928B', 'Staging - Lab 1', 'Test failed. App crashed when Night Mode was enabled.'),
('EXEC-1002', 'TC-CAM-0142', 'FAILED', 'SM-S928U', 'Staging - Lab 2', 'Image captured was extremely blurry. Does not meet quality thresholds.'),
('EXEC-1003', 'TC-CAM-0142', 'PASSED', 'SM-S928B', 'Production - OTA', 'Test passed after latest patch.')
ON CONFLICT DO NOTHING;

