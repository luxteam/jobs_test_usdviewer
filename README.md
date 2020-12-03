# Autotests for USDViewer

## Install
 1. Clone this repo
 2. Get `jobs_launcher` as git submodule, using next commands
 `git submodule init`
 `git submodule update`
 3. Check that `USDViewerAssets` scenes placed in `C:/TestResources`
 4. Place USD Viewer in root in directory with name USDViewer
 5. Add USDViewer/bin in exclusions of Windows Defender for prevent blocking of usdrecord utility
 6. Run `scripts/run.bat` with customised `--cmd_variables`