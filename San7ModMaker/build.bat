@echo off
chcp 65001 >nul
setlocal enabledelayedexpansion

:: ============================================================
::  San7ModMaker - 三国群英传7 MOD制作器 自动编译脚本
::  用法: build.bat [clean] [run]
::    clean  - 编译前清理旧的构建产物
::    run    - 编译后自动运行生成的EXE
:: ============================================================

title San7ModMaker 编译工具

set "PROJECT_DIR=%~dp0"
cd /d "%PROJECT_DIR%"

echo.
echo ========================================
echo   San7ModMaker 自动编译脚本
echo   三国群英传7 MOD制作器 V3.17.0
echo ========================================
echo.

:: --- 检查 Python ---
echo [1/5] 检查 Python 环境...
python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo [错误] 未找到 Python，请先安装 Python 3.10+
    echo         下载地址: https://www.python.org/downloads/
    pause
    exit /b 1
)
for /f "tokens=2" %%v in ('python --version 2^>^&1') do echo        已检测到 Python %%v

:: --- 检查/安装 PyInstaller ---
echo.
echo [2/5] 检查 PyInstaller...
python -c "import PyInstaller" >nul 2>&1
if %errorlevel% neq 0 (
    echo        正在安装 PyInstaller...
    pip install pyinstaller -q
    if %errorlevel% neq 0 (
        echo [错误] PyInstaller 安装失败
        pause
        exit /b 1
    )
)
echo        PyInstaller 已就绪

:: --- 安装项目依赖 ---
echo.
echo [3/5] 安装项目依赖...
pip install -r requirements.txt -q
if %errorlevel% neq 0 (
    echo [警告] 部分依赖安装失败，继续编译...
)
echo        依赖安装完成

:: --- 清理旧构建 ---
if /i "%~1"=="clean" (
    echo.
    echo [清理] 删除旧的构建产物...
    if exist "build" (
        rmdir /s /q "build"
        echo        已删除 build/
    )
    if exist "dist" (
        rmdir /s /q "dist"
        echo        已删除 dist/
    )
    if exist "*.spec.bak" (
        del /q "*.spec.bak"
        echo        已删除 .spec.bak
    )
)

:: --- 编译 EXE ---
echo.
echo [4/5] 开始编译 EXE...
echo        这可能需要几分钟，请耐心等待...
echo.

python -m PyInstaller build.spec --noconfirm --log-level=WARN

if %errorlevel% neq 0 (
    echo.
    echo [错误] 编译失败！请检查上方错误信息。
    echo        常见问题:
    echo          - 缺少依赖: pip install -r requirements.txt
    echo          - 磁盘空间不足
    echo          - 防病毒软件拦截
    pause
    exit /b 1
)

:: --- 检查产物 ---
echo.
echo [5/5] 检查编译产物...
if exist "dist\San7ModMaker\San7ModMaker.exe" (
    for %%F in ("dist\San7ModMaker\San7ModMaker.exe") do (
        set "size=%%~zF"
        set /a "size_mb=!size! / 1048576"
    )
    echo.
    echo ========================================
    echo   编译成功！
    echo   产物: dist\San7ModMaker\San7ModMaker.exe
    echo   大小: !size_mb! MB
    echo ========================================
    echo.
    
    :: --- 可选: 运行 ---
    if /i "%~2"=="run" (
        echo 正在启动 San7ModMaker...
        start "" "dist\San7ModMaker\San7ModMaker.exe"
    ) else if /i "%~1"=="run" (
        echo 正在启动 San7ModMaker...
        start "" "dist\San7ModMaker\San7ModMaker.exe"
    )
) else (
    echo.
    echo [错误] 未找到编译产物 dist\San7ModMaker\San7ModMaker.exe
    echo        请检查编译日志
    pause
    exit /b 1
)

endlocal