set PATH=c:\python35\;c:\python35\scripts\;%PATH%
python -m pip install -r ..\jobs_launcher\install\requirements.txt

set RETRIES=%3
set UPDATE_REFS=%4
if not defined RETRIES set RETRIES=2
if not defined UPDATE_REFS set UPDATE_REFS="No"

python ..\jobs_launcher\executeTests.py --tests_root ..\jobs --file_filter %1 --test_filter "%2" --work_root ..\Work\Results --work_dir USDViewer --cmd_variables Tool "..\\USDViewer\\bin\\usdrecord" ResPath "C:\\TestResources\\USDViewerAssets" retries %RETRIES% UpdateRefs %UPDATE_REFS%
