@echo off
chcp 65001 >nul
title San7ModMaker 编译打包脚本

echo ============================================
echo   San7ModMaker - 三国群英传7 MOD制作器
echo   编译打包脚本 (Windows)
echo ============================================
echo.

:: 检查 Python 是否安装
python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo [错误] 未检测到 Python，请先安装 Python 3.10+
    echo 下载地址: https://www.python.org/downloads/
    pause
    exit /b 1
)

echo [1/5] 检查 Python 环境...
python --version
echo.

:: 创建虚拟环境（可选，推荐）
if not exist "venv" (
    echo [2/5] 创建虚拟环境...
    python -m venv venv
    if %errorlevel% neq 0 (
        echo [错误] 创建虚拟环境失败
        pause
        exit /b 1
    )
)

:: 激活虚拟环境
call venv\Scripts\activate.bat
if %errorlevel% neq 0 (
    echo [错误] 激活虚拟环境失败
    pause
    exit /b 1
)

echo [3/5] 安装依赖...
pip install --upgrade pip -q
pip install -r requirements.txt
if %errorlevel% neq 0 (
    echo [错误] Python 依赖安装失败
    pause
    exit /b 1
)

:: 安装 Windows 必需依赖
echo [3/5] 安装 Windows 平台依赖 (pythonnet)...
pip install pythonnet
if %errorlevel% neq 0 (
    echo [警告] pythonnet 安装失败，请检查 .NET Framework 是否安装
    echo 如果编译仍失败，请手动安装: pip install pythonnet
)

:: 安装 PyInstaller
echo [3/5] 安装 PyInstaller...
pip install pyinstaller
if %errorlevel% neq 0 (
    echo [错误] PyInstaller 安装失败
    pause
    exit /b 1
)

echo.
echo [4/6] 完整性验证 (确保程序可启动)...
python validate.py
if %errorlevel% neq 0 (
    echo.
    echo [错误] 代码验证失败，请修复上方错误后重试
    echo   提示: 可单独运行 python validate.py 查看详细错误
    pause
    exit /b 1
)
echo [4/6] 验证通过!

echo.
echo [5/6] 开始编译...
pyinstaller build.spec --clean --noconfirm

if %errorlevel% neq 0 (
    echo.
    echo [错误] 编译失败，请检查上方错误信息
    echo 常见问题:
    echo   1. pythonnet 未正确安装
    echo   2. WebView2 Runtime 未安装
    echo   3. 杀毒软件拦截
    pause
    exit /b 1
)

echo.
echo [6/6] 编译完成!
echo.
echo ============================================
echo   输出文件: dist\San7ModMaker.exe
echo ============================================
echo.
echo 注意事项:
echo   1. 将 dist 文件夹整体复制到任意目录即可运行
echo   2. 用户电脑需安装 WebView2 Runtime
echo      (Win10 1809+ 已内置, Win7/8 需手动下载)
echo   3. 首次运行会自动创建配置文件在:
echo      %%APPDATA%%\San7ModMaker\san7mod_config.json
echo   4. MOD 数据将保存在 exe 所在目录的 mods/ exports/ 下
echo.
echo ============================================

:: 询问是否打开输出目录
set /p open="是否打开输出目录? (Y/N): "
if /i "%open%"=="Y" (
    explorer dist
)

pause