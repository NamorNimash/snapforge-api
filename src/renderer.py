import asyncio
from pathlib import Path
from playwright.async_api import async_playwright

async def take_screenshot(
    url: str,
    output_path: Path,
    format: str = "png",
    full_page: bool = True,
    width: int = 1280,
    height: int = 720
):
    """Render a page and take a screenshot.
    
    Uses process-per-render: fresh browser context per call.
    Slower than pool but zero memory leaks.
    """
    async with async_playwright() as p:
        browser = await p.chromium.launch(
            headless=True,
            args=[
                "--no-sandbox",
                "--disable-setuid-sandbox",
                "--disable-dev-shm-usage",
                "--disable-accelerated-2d-canvas",
                "--no-first-run",
                "--no-zygote",
                "--single-process",
                "--disable-gpu"
            ]
        )
        context = await browser.new_context(
            viewport={"width": width, "height": height},
            accept_downloads=False
        )
        page = await context.new_page()
        
        try:
            await page.goto(url, wait_until="networkidle", timeout=20000)
            
            if full_page:
                await page.screenshot(
                    path=str(output_path),
                    type=format,
                    full_page=True
                )
            else:
                await page.screenshot(
                    path=str(output_path),
                    type=format
                )
        finally:
            await context.close()
            await browser.close()

async def generate_pdf(
    url: str,
    output_path: Path,
    width: int = 1280,
    height: int = 720
):
    """Render a page and generate PDF.
    
    Same process-per-render model as screenshot.
    """
    async with async_playwright() as p:
        browser = await p.chromium.launch(
            headless=True,
            args=[
                "--no-sandbox",
                "--disable-setuid-sandbox",
                "--disable-dev-shm-usage",
                "--disable-accelerated-2d-canvas",
                "--no-first-run",
                "--no-zygote",
                "--single-process",
                "--disable-gpu"
            ]
        )
        context = await browser.new_context(
            viewport={"width": width, "height": height}
        )
        page = await context.new_page()
        
        try:
            await page.goto(url, wait_until="networkidle", timeout=20000)
            
            await page.pdf(
                path=str(output_path),
                format="A4",
                print_background=True,
                margin={
                    "top": "1cm",
                    "right": "1cm", 
                    "bottom": "1cm",
                    "left": "1cm"
                }
            )
        finally:
            await context.close()
            await browser.close()
