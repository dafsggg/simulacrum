@echo off
chcp 65001 >nul
echo ========================================
echo   世界杯预测系统 - Windows 打包脚本
echo ========================================
echo.

cd /d "%~dp0"

echo [1/4] 清理旧的打包产物...
if exist build rmdir /s /q build
if exist dist rmdir /s /q dist
echo 完成。
echo.

echo [2/4] 检查 PyInstaller...
python -m PyInstaller --version >nul 2>&1
if errorlevel 1 (
  echo 未找到 PyInstaller，正在安装...
  pip install pyinstaller
  if errorlevel 1 (
    echo.
    echo [错误] PyInstaller 安装失败！
    pause
    exit /b 1
  )
)
echo PyInstaller 就绪。
echo.

echo [3/4] 开始打包（onedir 模式）...
echo   这可能需要 1-2 分钟，请耐心等待...
echo.

python -m PyInstaller --clean cup2026predictor.spec

if errorlevel 1 (
  echo.
  echo [错误] 打包失败！
  pause
  exit /b 1
)

echo.
echo [4/4] 打包完成！
echo.
echo 输出目录: dist\世界杯预测系统\
echo 主程序: dist\世界杯预测系统\世界杯预测系统.exe
echo.
echo 使用方法：
echo   1. 将 dist\世界杯预测系统 整个文件夹复制给用户
echo   2. 用户双击文件夹内的 "世界杯预测系统.exe"
echo   3. 等待自动打开浏览器
echo   4. 点击右下角"更新预测"按钮联网更新数据
echo.
pause
