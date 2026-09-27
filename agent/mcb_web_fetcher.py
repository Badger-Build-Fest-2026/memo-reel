"""FastMCP Server to fetch, extract clean markdown, and summarize URLs found in reel links."""

from __future__ import annotations

from bs4 import BeautifulSoup
from fastmcp import FastMCP
import httpx
from markdownify import markdownify as md

mcp = FastMCP("ReelWebEnricher")


@mcp.tool
def enrich_from_web(url: str, max_chars: int = 2500) -> str:
  """Fetch external web page content and return clean markdown text."""
  headers = {
      "User-Agent": (
          "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
      )
  }
  try:
    with httpx.Client(
        timeout=8.0, follow_redirects=True, headers=headers
    ) as client:
      resp = client.get(url)
      resp.raise_for_status()

    soup = BeautifulSoup(resp.text, "html.parser")
    for element in soup(
        ["script", "style", "nav", "footer", "header", "noscript"]
    ):
      element.decompose()

    body = soup.body or soup
    markdown_text = md(str(body), heading_style="ATX").strip()
    cleaned = "\n".join(
        [line for line in markdown_text.splitlines() if line.strip()]
    )
    return cleaned[:max_chars] if cleaned else "No body text extracted."
  except Exception as exc:
    return f"Failed to retrieve {url}: {type(exc).__name__}: {exc}"


if __name__ == "__main__":
  mcp.run()