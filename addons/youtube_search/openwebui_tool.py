"""
title: YouTube Video Search
author: Autotech AI
version: 0.2.0
description: Search YouTube for automotive repair videos from trusted channels
"""

import aiohttp
import urllib.parse
import re
from typing import Callable, Any
from starlette.responses import HTMLResponse


class Tools:
    def __init__(self):
        # SearXNG instance URL (runs on poweredge1)
        self.searxng_url = "http://poweredge1:8082"
        
        # Trusted automotive YouTube channels
        # Add or remove channels as needed
        self.trusted_channels = [
            "ChrisFix",
            "South Main Auto Repair",
            "Scanner Danner",
            "Pine Hollow Auto Diagnostics",
            "Weber Auto",
            "Rainman Ray's Repairs",
            "Watch Wes Work",
            "FordTechMakuloco",
            "EricTheCarGuy",
            "Scotty Kilmer",
            "1A Auto",
        ]

    async def search_youtube(
        self,
        query: str,
        __event_emitter__: Callable[[dict], Any] = None,
    ) -> HTMLResponse:
        """
        Search YouTube for automotive repair videos. ONLY use this tool when the user explicitly asks for a video, tutorial, or visual demonstration. Do NOT use for general diagnostic questions or spec lookups.
        
        :param query: What to search for (e.g., "alternator replacement 2015 Honda Civic")
        :return: Embedded YouTube video player
        """
        
        if __event_emitter__:
            await __event_emitter__({
                "type": "status",
                "data": {"description": "Searching YouTube...", "done": False}
            })
        
        # Build search query with channel preferences
        channel_query = " OR ".join([f'"{ch}"' for ch in self.trusted_channels[:5]])
        full_query = f"{query} ({channel_query})"
        
        try:
            # Query SearXNG with YouTube engine
            params = {
                "q": full_query,
                "format": "json",
                "engines": "youtube",
                "categories": "videos",
            }
            
            url = f"{self.searxng_url}/search?{urllib.parse.urlencode(params)}"
            
            async with aiohttp.ClientSession() as session:
                async with session.get(url, timeout=aiohttp.ClientTimeout(total=15)) as resp:
                    if resp.status != 200:
                        return f"❌ SearXNG error: HTTP {resp.status}"
                    
                    data = await resp.json()
            
            results = data.get("results", [])
            
            if not results:
                if __event_emitter__:
                    await __event_emitter__({
                        "type": "status",
                        "data": {"description": "No videos found", "done": True}
                    })
                return f"No YouTube videos found for: {query}"
            
            # Find best match - prefer trusted channels
            best_result = None
            for result in results:
                channel = result.get("author", result.get("channel", ""))
                if any(tc.lower() in channel.lower() for tc in self.trusted_channels):
                    best_result = result
                    break
            
            # Fall back to first result if no trusted channel found
            if not best_result:
                best_result = results[0]
            
            # Extract video info
            video_url = best_result.get("url", "")
            title = best_result.get("title", "Unknown Title")
            channel = best_result.get("author", best_result.get("channel", "Unknown Channel"))
            
            # Extract video ID for embed
            video_id = None
            if "youtube.com/watch?v=" in video_url:
                video_id = video_url.split("v=")[1].split("&")[0]
            elif "youtu.be/" in video_url:
                video_id = video_url.split("youtu.be/")[1].split("?")[0]
            
            if __event_emitter__:
                await __event_emitter__({
                    "type": "status",
                    "data": {"description": f"Found: {title}", "done": True}
                })
            
            if video_id:
                # Return HTMLResponse with inline Content-Disposition for iframe embed
                html_content = f'''
                <div style="padding: 10px;">
                    <h3>🎬 {title}</h3>
                    <p><strong>Channel:</strong> {channel}</p>
                    <iframe 
                        width="560" 
                        height="315" 
                        src="https://www.youtube-nocookie.com/embed/{video_id}" 
                        frameborder="0" 
                        allow="accelerometer; autoplay; clipboard-write; encrypted-media; gyroscope; picture-in-picture" 
                        allowfullscreen>
                    </iframe>
                </div>
                '''
                return HTMLResponse(
                    content=html_content,
                    status_code=200,
                    headers={"Content-Disposition": "inline"}
                )
            else:
                return f"## 🎬 {title}\n\n**Channel:** {channel}\n\n▶️ **[Watch Video]({video_url})**"
            
        except aiohttp.ClientError as e:
            return f"❌ Network error: {str(e)}"
        except Exception as e:
            return f"❌ Error searching YouTube: {str(e)}"
        except Exception as e:
            return f"❌ Error searching YouTube: {str(e)}"
