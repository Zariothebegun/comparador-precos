@echo off
setlocal
cd /d "%~dp0"

set "PATH=%USERPROFILE%\.local\bin;%PATH%"

where uv >nul 2>nul
if errorlevel 1 (
  echo.
  echo   O uv nao foi encontrado.
  echo   Instala primeiro: https://docs.astral.sh/uv/
  echo.
  pause
  exit /b 1
)

echo.
echo   Comparador de Precos - Portugal
echo   A arrancar em http://127.0.0.1:8770/
echo   Para parar: Ctrl+C
echo.

uv run --no-project --python 3.14 python app.py --abrir

echo.
echo   Servidor terminado.
pause
