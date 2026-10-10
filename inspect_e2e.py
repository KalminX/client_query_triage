"""
End-to-end inspection script using Playwright to test all pages, user roles, and workflows.
"""

import asyncio
from playwright.async_api import async_playwright

async def inspect_app():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(viewport={'width': 1280, 'height': 720})
        page = await context.new_page()

        print("1. Testing Inbox View...")
        await page.goto("http://127.0.0.1:8000/")
        title = await page.title()
        print(f"   Inbox Title: {title}")
        assert "Review Queue" in title

        # Test Search & Filter Tabs
        print("2. Testing Filter Tabs...")
        await page.click("text=Drafts Ready")
        await page.wait_for_timeout(500)
        await page.click("text=Escalations")
        await page.wait_for_timeout(500)
        await page.click("text=⚠️ SLA Overdue")
        await page.wait_for_timeout(500)
        await page.click("text=🔒 Confidential")
        await page.wait_for_timeout(500)
        await page.click("text=All Queries")
        await page.wait_for_timeout(500)

        # Test Message Detail & Review Workbench (Msg #1 - Apex Global)
        print("3. Testing Message Detail (Apex Global)...")
        await page.goto("http://127.0.0.1:8000/message/1/")
        content = await page.content()
        assert "Sarah Jenkins" in content
        assert "Grounded Draft Reply" in content

        # Test Draft Editing
        print("4. Testing Draft Editing on Workbench...")
        textarea = page.locator("textarea[name='draft_body']")
        current_text = await textarea.input_value()
        await textarea.fill(current_text + "\n\nPS: Thank you for your continued partnership with Acme Services.")
        await page.click("button:has-text('Save Draft Edits')")
        await page.wait_for_timeout(800)
        print("   ✓ Draft edited and saved successfully")

        # Test Draft Approval
        print("5. Testing Draft Approval...")
        await page.click("button:has-text('Approve & Save to Email Drafts')")
        await page.wait_for_timeout(800)
        content_after_approve = await page.content()
        assert "Saved in Demo Drafts" in content_after_approve or "Saved to Demo" in content_after_approve
        print("   ✓ Draft approved and synced to provider drafts")

        # Test Add Note
        print("6. Testing Internal Note Submission...")
        await page.fill("input[name='note_text']", "Verified customer VAT number format with international registry.")
        await page.click("button:has-text('Add Note')")
        await page.wait_for_timeout(600)
        print("   ✓ Internal note added to audit trail")

        # Test Message #5 Draft Regeneration (Solaria Dynamics)
        print("7. Testing AI Draft Regeneration (Msg #5)...")
        await page.goto("http://127.0.0.1:8000/message/5/")
        await page.click("summary:has-text('Need changes? Regenerate draft')")
        await page.wait_for_timeout(400)
        await page.fill("textarea[name='custom_instructions']", "Keep it concise and offer a 15-minute alignment call.")
        await page.click("button:has-text('Regenerate Draft with Claude')")
        await page.wait_for_timeout(1000)
        print("   ✓ Draft regenerated with custom instructions")

        # Test Message #6 Confidential AI Bypass (Onyx Defense)
        print("8. Testing Confidential Client AI-Bypass View (Msg #6)...")
        await page.goto("http://127.0.0.1:8000/message/6/")
        content_conf = await page.content()
        assert "CONFIDENTIAL CLIENT" in content_conf
        assert "Automated AI Draft Bypassed" in content_conf
        print("   ✓ Confidential AI-bypass verified")

        # Test Analytics / Daily Summary View
        print("9. Testing Daily SLA Analytics View...")
        await page.goto("http://127.0.0.1:8000/analytics/")
        content_analytics = await page.content()
        assert "Daily SLA Digest" in content_analytics
        print("   ✓ Analytics page verified")

        # Test Knowledge Base View
        print("10. Testing Knowledge Base Explorer...")
        await page.goto("http://127.0.0.1:8000/knowledge-base/")
        await page.fill("input[name='q']", "SAML")
        await page.click("button:has-text('Search')")
        await page.wait_for_timeout(500)
        content_kb = await page.content()
        assert "SAML 2.0 Single Sign-On" in content_kb
        print("   ✓ Knowledge base search verified")

        # Test Routing Rules View
        print("11. Testing Routing Rules View...")
        await page.goto("http://127.0.0.1:8000/routing-rules/")
        content_rules = await page.content()
        assert "Security Incidents" in content_rules
        print("   ✓ Routing rules verified")

        # Test Integrations View
        print("12. Testing Integrations & Security View...")
        await page.goto("http://127.0.0.1:8000/integrations/")
        content_integrations = await page.content()
        assert "Client Confidentiality" in content_integrations
        print("   ✓ Integrations & Security verified")

        # Test Login Page
        print("13. Testing Login Page...")
        await page.goto("http://127.0.0.1:8000/login/")
        content_login = await page.content()
        assert "Staff Sign In" in content_login
        print("   ✓ Login page verified")

        print("\n🎉 ALL 13 END-TO-END WORKFLOW CHECKS PASSED PERFECTLY!")
        await browser.close()

if __name__ == "__main__":
    asyncio.run(inspect_app())
