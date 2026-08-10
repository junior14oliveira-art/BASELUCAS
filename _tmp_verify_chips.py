from pathlib import Path
import re

p = Path(r"G:\Meu Drive\BASE ANTIGRAVITY\apps\api\src\presentation\routers\web_ui.py")
text = p.read_text(encoding="utf-8")
print("filterByChannel", text.count("filterByChannel"))
print("activeChannelFilter", text.count("activeChannelFilter"))
print("chip All", "filterByChannel('All')" in text)
