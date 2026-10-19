@echo off
REM Helper script to run npm commands using the locally available Node.js
REM Usage: npm-run.cmd install
REM        npm-run.cmd run dev
REM        npm-run.cmd run build

SET NODE_PATH=C:\Users\Anushka\AppData\Local\ms-playwright-go\1.50.1
SET NPM_CLI=C:\Users\Anushka\AppData\Local\npm-standalone\npm\bin\npm-cli.js
SET PATH=%NODE_PATH%;%PATH%

"%NODE_PATH%\node.exe" "%NPM_CLI%" %*
