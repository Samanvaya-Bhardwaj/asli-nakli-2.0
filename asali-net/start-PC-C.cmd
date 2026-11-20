@echo off
rem Starts PC-C's share of the four-computer run: Docker, databases, Python, portal, data and the organisations.
rem Double-click it, or run it in a terminal. Extra options: -Fresh (reload the seeded data), -Stop (stop).
rem Leave the window open while the demo runs; closing it or pressing Ctrl+C stops this computer's organisations.
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0infra\scripts\start-pc.ps1" -Pc PC-C %*
if errorlevel 1 pause
