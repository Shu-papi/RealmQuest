@echo off
rem ==========================================================================================
rem  Build RealmQuest.exe (a folder build) and zip it:  build_exe.bat
rem    dist\RealmQuest\RealmQuest.exe          the game
rem    dist\RealmQuest\_internal\              Python + the game's code
rem    dist\RealmQuest\assets, audio, config   the data (config\*.toml can be edited while it runs)
rem    dist\RealmQuest.zip                     everything above, ready to share
rem  Needs: pip install -r requirements.txt   (pygame-ce, pyinstaller)
rem  Saves go to %APPDATA%\RealmQuest (never into the game folder).
rem ==========================================================================================
setlocal
cd /d "%~dp0"
set OUT=dist\RealmQuest

python tools\make_icon.py || goto :fail
python -m PyInstaller --noconfirm --clean RealmQuest.spec || goto :fail

rem ---- data next to the .exe (same layout as the repo) ----
robocopy assets "%OUT%\assets" /E /NFL /NDL /NJH /NJS /XD source /XF preview_*.png *.md *.gpl .gitkeep >nul
if errorlevel 8 goto :fail
robocopy audio\music "%OUT%\audio\music" *.mp3 *.ogg *.wav /NFL /NDL /NJH /NJS >nul
if errorlevel 8 goto :fail
robocopy config "%OUT%\config" /E /NFL /NDL /NJH /NJS /XD presets /XF *.md >nul
if errorlevel 8 goto :fail
robocopy characters\kendi_pygame\assets "%OUT%\characters\kendi_pygame\assets" /E /NFL /NDL /NJH /NJS /XF *.md .gitkeep >nul
if errorlevel 8 goto :fail
rem ---- the 3 files the game loads from disk are shipped COMPILED (no readable source in the package) ----
python tools\compile_for_build.py "%OUT%" characters\kendi_pygame\kendi_sprites.py:characters\kendi_pygame src\characters\player.py:src\characters src\characters\elf_code\sprite_animation\config.py:src\characters\elf_code\sprite_animation || goto :fail
copy /y docs_player\README_PLAYERS.txt "%OUT%\README.txt" >nul
copy /y docs_player\CREDITS.txt "%OUT%\CREDITS.txt" >nul

rem ---- strip leaks, then refuse to continue if the package holds source / saves / personal strings ----
python tools\sanitize_build.py "%OUT%" || goto :fail

rem ---- self-test the build, then zip it ----
"%OUT%\RealmQuest.exe" --smoke 600 --class warrior
if errorlevel 1 goto :fail
"%OUT%\RealmQuest.exe" --smoke 600 --class mage
if errorlevel 1 goto :fail
"%OUT%\RealmQuest.exe" --smoke 600 --class archer
if errorlevel 1 goto :fail
powershell -NoProfile -Command "Compress-Archive -Path '%OUT%' -DestinationPath 'dist\RealmQuest.zip' -Force" || goto :fail
echo.
echo Built %OUT%\RealmQuest.exe and dist\RealmQuest.zip
exit /b 0

:fail
echo.
echo BUILD FAILED
exit /b 1
