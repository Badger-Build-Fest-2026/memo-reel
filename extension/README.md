### This folder contains all the code related to the Chrome extension

Load this directory as an unpacked Chrome extension and use it on an Instagram
Reel page. The local API URL is configured in `reel-actions.js` and defaults to
`http://127.0.0.1:8000/api/v1/reels/submit`. It must use `http://` because the
local FastAPI server does not provide TLS. If Docker Compose maps the API to a
different host port, update the URL there and the matching host permission in
`manifest.json`, then reload the extension from `chrome://extensions`.

The extractor uses the profile link's URL/ARIA label (for example,
`/techtalkuk/reels/` and `techtalkuk reels`) rather than Instagram's generated
CSS class names. It reads caption text associated with the visible Reel video;
it does not use the longest text on the whole Instagram page as a fallback.
For captions with linked hashtags, it finds the caption block using
`dir="auto"` and tag links whose URL contains `/explore/tags/`, removes those
links from the caption text, and sends their visible `#tag` labels separately.
This avoids depending on changing generated classes. It sends hashtags as a
space-separated string to match the backend request schema. If it cannot
identify the author, it asks you to retry instead of saving generic page text
such as “Profile”.
