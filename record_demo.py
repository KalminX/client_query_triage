"""
Automated Screen Recording & Demonstration Generator for AI Client Query Triage.
Produces 1280x720 30FPS H.264 MP4 video with smooth visible cursor tracking and realistic interactions.
"""

import asyncio
import os
import shutil
import subprocess
from playwright.async_api import async_playwright

# Helper script injected into every page to render a visible animated mouse cursor
CURSOR_INJECTION_JS = """
(() => {
    if (window.__cursorInjected) return;
    window.__cursorInjected = true;

    const cursor = document.createElement('div');
    cursor.id = 'playwright-custom-cursor';
    cursor.style.position = 'fixed';
    cursor.style.top = '0px';
    cursor.style.left = '0px';
    cursor.style.width = '20px';
    cursor.style.height = '20px';
    cursor.style.borderRadius = '50%';
    cursor.style.backgroundColor = 'rgba(14, 165, 233, 0.7)';
    cursor.style.border = '2px solid #ffffff';
    cursor.style.boxShadow = '0 0 10px rgba(14, 165, 233, 0.8), 0 2px 4px rgba(0,0,0,0.5)';
    cursor.style.pointerEvents = 'none';
    cursor.style.zIndex = '999999';
    cursor.style.transition = 'transform 0.08s ease-out, background-color 0.15s ease';
    cursor.style.transform = 'translate(-50%, -50%)';
    cursor.style.display = 'block';
    document.body.appendChild(cursor);

    const clickRing = document.createElement('div');
    clickRing.id = 'playwright-click-ring';
    clickRing.style.position = 'fixed';
    clickRing.style.width = '36px';
    clickRing.style.height = '36px';
    clickRing.style.borderRadius = '50%';
    clickRing.style.border = '2px solid #38bdf8';
    clickRing.style.pointerEvents = 'none';
    clickRing.style.zIndex = '999998';
    clickRing.style.opacity = '0';
    clickRing.style.transform = 'translate(-50%, -50%) scale(0.5)';
    clickRing.style.transition = 'transform 0.25s ease-out, opacity 0.25s ease-out';
    document.body.appendChild(clickRing);

    window.updateCursorPos = (x, y) => {
        cursor.style.left = x + 'px';
        cursor.style.top = y + 'px';
    };

    window.triggerClickEffect = (x, y) => {
        cursor.style.backgroundColor = '#f43f5e';
        clickRing.style.left = x + 'px';
        clickRing.style.top = y + 'px';
        clickRing.style.opacity = '1';
        clickRing.style.transform = 'translate(-50%, -50%) scale(1.4)';

        setTimeout(() => {
            cursor.style.backgroundColor = 'rgba(14, 165, 233, 0.7)';
            clickRing.style.opacity = '0';
            clickRing.style.transform = 'translate(-50%, -50%) scale(0.5)';
        }, 250);
    };

    document.addEventListener('mousemove', (e) => {
        window.updateCursorPos(e.clientX, e.clientY);
    });
})();
"""


async def smooth_move(page, start_x, start_y, target_x, target_y, steps=25, delay=0.015):
    """Interpolate smooth cursor path between two coordinates."""
    for i in range(1, steps + 1):
        t = i / steps
        # Smooth easeInOut curve
        ease_t = t * t * (3 - 2 * t)
        curr_x = start_x + (target_x - start_x) * ease_t
        curr_y = start_y + (target_y - start_y) * ease_t
        await page.mouse.move(curr_x, curr_y)
        await page.evaluate(f"window.updateCursorPos && window.updateCursorPos({curr_x}, {curr_y})")
        await asyncio.sleep(delay)


async def click_element_smoothly(page, locator, current_pos, steps=20):
    """Smoothly move to an element, animate cursor click, and trigger click."""
    box = await locator.bounding_box()
    if not box:
        return current_pos

    target_x = box['x'] + box['width'] / 2
    target_y = box['y'] + box['height'] / 2

    await smooth_move(page, current_pos[0], current_pos[1], target_x, target_y, steps=steps)
    await page.evaluate(f"window.triggerClickEffect && window.triggerClickEffect({target_x}, {target_y})")
    await locator.click()
    await asyncio.sleep(0.3)
    return (target_x, target_y)


async def type_smoothly(page, text, delay=0.04):
    """Type characters with realistic human timing."""
    for char in text:
        await page.keyboard.type(char)
        await asyncio.sleep(delay)


async def record_demo():
    output_dir = "recordings_raw"
    if os.path.exists(output_dir):
        shutil.rmtree(output_dir)
    os.makedirs(output_dir, exist_ok=True)

    # Reset/reseed fresh fixture state so demo is clean
    subprocess.run(["./venv/bin/python", "manage.py", "seed_demo"], check=True)

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(
            viewport={'width': 1280, 'height': 720},
            record_video_dir=output_dir,
            record_video_size={'width': 1280, 'height': 720}
        )

        page = await context.new_page()
        
        # Inject custom visible cursor on every frame/navigation
        page.on("load", lambda: asyncio.create_task(page.evaluate(CURSOR_INJECTION_JS)))

        cursor_pos = (640, 360)

        print("🎬 Starting demo recording walkthrough...")

        # =====================================================================
        # SCENE 1: Review Queue Overview & Live Filtering
        # =====================================================================
        print("  • Scene 1: Review Queue Overview & Live Filtering")
        await page.goto("http://127.0.0.1:8000/")
        await page.evaluate(CURSOR_INJECTION_JS)
        await asyncio.sleep(1.2)

        # Move around header and filters
        cursor_pos = await click_element_smoothly(page, page.locator("a:has-text('Drafts Ready')"), cursor_pos)
        await asyncio.sleep(1.0)

        cursor_pos = await click_element_smoothly(page, page.locator("a:has-text('Escalations')"), cursor_pos)
        await asyncio.sleep(1.0)

        cursor_pos = await click_element_smoothly(page, page.locator("a:has-text('⚠️ SLA Overdue')"), cursor_pos)
        await asyncio.sleep(1.0)

        cursor_pos = await click_element_smoothly(page, page.locator("a:has-text('🔒 Confidential')"), cursor_pos)
        await asyncio.sleep(1.0)

        cursor_pos = await click_element_smoothly(page, page.locator("a:has-text('All Queries')"), cursor_pos)
        await asyncio.sleep(1.0)

        # Search filter
        search_input = page.locator("input[name='q']")
        cursor_pos = await click_element_smoothly(page, search_input, cursor_pos)
        await type_smoothly(page, "invoice")
        await asyncio.sleep(1.2)
        await page.keyboard.press("Meta+A")
        await page.keyboard.press("Backspace")
        await asyncio.sleep(1.0)

        # =====================================================================
        # SCENE 2: Detailed Review Workbench (Msg #1 - Apex Global Billing)
        # =====================================================================
        print("  • Scene 2: Review Workbench & Grounded Draft Approval (Apex Global)")
        first_review_btn = page.locator("table tbody tr:first-child a:has-text('Review')")
        cursor_pos = await click_element_smoothly(page, first_review_btn, cursor_pos)
        await page.wait_for_load_state("networkidle")
        await page.evaluate(CURSOR_INJECTION_JS)
        await asyncio.sleep(1.5)

        # Hover over Client SLA Policy and AI Triage Card
        await smooth_move(page, cursor_pos[0], cursor_pos[1], 300, 200, steps=25)
        cursor_pos = (300, 200)
        await asyncio.sleep(0.8)

        await smooth_move(page, cursor_pos[0], cursor_pos[1], 300, 420, steps=25)
        cursor_pos = (300, 420)
        await asyncio.sleep(0.8)

        # Focus textarea and make manual reviewer edit
        draft_textarea = page.locator("textarea[name='draft_body']")
        cursor_pos = await click_element_smoothly(page, draft_textarea, cursor_pos)
        await page.keyboard.press("Control+End")
        await page.keyboard.type("\n\nPS: Thank you for your continued business with Acme Services.")
        await asyncio.sleep(0.8)

        # Save Edits
        save_btn = page.locator("button:has-text('Save Draft Edits')")
        cursor_pos = await click_element_smoothly(page, save_btn, cursor_pos)
        await asyncio.sleep(1.2)

        # Approve and Sync to Drafts
        approve_btn = page.locator("button:has-text('Approve & Save to Email Drafts')")
        cursor_pos = await click_element_smoothly(page, approve_btn, cursor_pos)
        await asyncio.sleep(1.8)

        # Add internal note
        note_input = page.locator("input[name='note_text']")
        cursor_pos = await click_element_smoothly(page, note_input, cursor_pos)
        await type_smoothly(page, "Verified client VAT certificate format against HMRC database.")
        add_note_btn = page.locator("button:has-text('Add Note')")
        cursor_pos = await click_element_smoothly(page, add_note_btn, cursor_pos)
        await asyncio.sleep(1.2)

        # =====================================================================
        # SCENE 3: AI Draft Regeneration (Msg #5 - Solaria Dynamics Ambiguity)
        # =====================================================================
        print("  • Scene 3: AI Regeneration on Ambiguous Request (Solaria Dynamics)")
        await page.goto("http://127.0.0.1:8000/message/5/")
        await page.evaluate(CURSOR_INJECTION_JS)
        await asyncio.sleep(1.5)

        # Open regeneration accordion
        regen_summary = page.locator("summary:has-text('Need changes? Regenerate draft')")
        cursor_pos = await click_element_smoothly(page, regen_summary, cursor_pos)
        await asyncio.sleep(0.8)

        # Type custom prompt
        custom_input = page.locator("textarea[name='custom_instructions']")
        cursor_pos = await click_element_smoothly(page, custom_input, cursor_pos)
        await type_smoothly(page, "Keep response under 3 sentences and offer a 10-minute alignment call.")
        await asyncio.sleep(0.6)

        regen_btn = page.locator("button:has-text('Regenerate Draft with Claude')")
        cursor_pos = await click_element_smoothly(page, regen_btn, cursor_pos)
        await asyncio.sleep(1.8)

        # =====================================================================
        # SCENE 4: Security Policy Guardrail (Msg #6 - Confidential Client)
        # =====================================================================
        print("  • Scene 4: Confidential Client Security Policy Guardrail (Onyx Defense)")
        await page.goto("http://127.0.0.1:8000/message/6/")
        await page.evaluate(CURSOR_INJECTION_JS)
        await asyncio.sleep(1.8)

        # =====================================================================
        # SCENE 5: Critical Emergency & Security Overrides (Msg #4 - Vanguard)
        # =====================================================================
        print("  • Scene 5: Critical Emergency & Deterministic Overrides (Vanguard FinTech)")
        await page.goto("http://127.0.0.1:8000/message/4/")
        await page.evaluate(CURSOR_INJECTION_JS)
        await asyncio.sleep(1.8)

        # =====================================================================
        # SCENE 6: Daily SLA Analytics & Digest Dashboard
        # =====================================================================
        print("  • Scene 6: Daily SLA Digest & Analytics")
        nav_analytics = page.locator("aside nav a:has-text('Daily SLA Digest')")
        cursor_pos = await click_element_smoothly(page, nav_analytics, cursor_pos)
        await page.wait_for_load_state("networkidle")
        await page.evaluate(CURSOR_INJECTION_JS)
        await asyncio.sleep(2.0)

        # =====================================================================
        # SCENE 7: Knowledge Base & Policy Grounding Store
        # =====================================================================
        print("  • Scene 7: Knowledge Base Explorer")
        nav_kb = page.locator("aside nav a:has-text('Knowledge Base')")
        cursor_pos = await click_element_smoothly(page, nav_kb, cursor_pos)
        await page.wait_for_load_state("networkidle")
        await page.evaluate(CURSOR_INJECTION_JS)
        await asyncio.sleep(1.5)

        kb_search = page.locator("input[name='q']")
        cursor_pos = await click_element_smoothly(page, kb_search, cursor_pos)
        await type_smoothly(page, "SAML")
        search_btn = page.locator("button:has-text('Search')")
        cursor_pos = await click_element_smoothly(page, search_btn, cursor_pos)
        await asyncio.sleep(1.8)

        # =====================================================================
        # SCENE 8: Routing Rules & Integrations
        # =====================================================================
        print("  • Scene 8: Routing Rules & Security Integrations")
        nav_rules = page.locator("aside nav a:has-text('Routing Rules')")
        cursor_pos = await click_element_smoothly(page, nav_rules, cursor_pos)
        await page.wait_for_load_state("networkidle")
        await page.evaluate(CURSOR_INJECTION_JS)
        await asyncio.sleep(1.5)

        nav_integ = page.locator("aside nav a:has-text('Security & Config')")
        cursor_pos = await click_element_smoothly(page, nav_integ, cursor_pos)
        await page.wait_for_load_state("networkidle")
        await page.evaluate(CURSOR_INJECTION_JS)
        await asyncio.sleep(2.0)

        # Return to main inbox as closing shot
        nav_inbox = page.locator("aside nav a:has-text('Review Queue')")
        cursor_pos = await click_element_smoothly(page, nav_inbox, cursor_pos)
        await page.wait_for_load_state("networkidle")
        await page.evaluate(CURSOR_INJECTION_JS)
        await asyncio.sleep(2.0)

        print("🎬 Walkthrough complete. Closing browser context...")
        await context.close()
        await browser.close()

    # Find the generated video in recordings_raw and transcode to optimized MP4
    video_files = [f for f in os.listdir(output_dir) if f.endswith(".webm") or f.endswith(".mp4")]
    if not video_files:
        raise RuntimeError("No recorded video found in output directory.")

    raw_video_path = os.path.join(output_dir, video_files[0])
    final_video_path = "demo_triage_assistant_walkthrough.mp4"

    print(f"🔄 Transcoding {raw_video_path} to {final_video_path} (1280x720 30FPS H.264)...")
    ffmpeg_cmd = [
        "ffmpeg", "-y",
        "-i", raw_video_path,
        "-vf", "scale=1280:720:force_original_aspect_ratio=decrease,pad=1280:720:(ow-iw)/2:(oh-ih)/2,format=yuv420p",
        "-r", "30",
        "-c:v", "libx264",
        "-preset", "medium",
        "-crf", "23",
        "-movflags", "+faststart",
        final_video_path
    ]
    subprocess.run(ffmpeg_cmd, check=True)
    print(f"✅ Final video successfully created: {final_video_path}")

if __name__ == "__main__":
    asyncio.run(record_demo())
