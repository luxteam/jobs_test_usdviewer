import argparse
import sys
import os
import subprocess
import psutil
import json
import shutil
import time
import datetime
import platform
import copy
import math
import traceback
from PIL import Image
from glob import glob
from utils import is_case_skipped

ROOT_DIR_PATH = os.path.abspath(os.path.join(os.path.dirname(__file__), os.path.pardir, os.path.pardir))
sys.path.append(ROOT_DIR_PATH)
from jobs_launcher.core.config import *
from jobs_launcher.core.system_info import get_gpu


# dict of settings which must be set in usda file and merged with target scene
USDA_SETTINGS = {"renderQuality": {"type": "token"}}


def create_args_parser():
    parser = argparse.ArgumentParser()
    parser.add_argument('--tool', required=True, metavar="<path>")
    parser.add_argument('--tests_list', required=True, metavar="<path>")
    parser.add_argument('--output_dir', required=True)
    parser.add_argument('--scene_path', required=True)
    parser.add_argument('--test_group', required=True)
    parser.add_argument('--retries', required=False, default=2, type=int)
    parser.add_argument('--update_refs', required=True)
    return parser.parse_args()


def get_images_list(work_dir):
    found_images = []
    found_images.extend(glob(os.path.join(os.path.join(work_dir, "*.png"))))
    found_images.extend(glob(os.path.join(os.path.join(work_dir, "*.jpg"))))
    return found_images


def copy_baselines(test, baseline_path, baseline_path_tr):
    try:
        shutil.copyfile(os.path.join(baseline_path_tr, test['name'] + CASE_REPORT_SUFFIX),
                 os.path.join(baseline_path, test['name'] + CASE_REPORT_SUFFIX))

        with open(os.path.join(baseline_path, test['name'] + CASE_REPORT_SUFFIX)) as baseline:
            baseline_json = json.load(baseline)

        for thumb in [''] + THUMBNAIL_PREFIXES:
            if os.path.exists(os.path.join(baseline_path_tr, baseline_json[thumb + 'render_color_path'])):
                shutil.copyfile(os.path.join(baseline_path_tr, baseline_json[thumb + 'render_color_path']),
                         os.path.join(baseline_path, baseline_json[thumb + 'render_color_path']))
    except:
        main_logger.error('Failed to copy baseline ' +
                                      os.path.join(baseline_path_tr, test['name'] + CASE_REPORT_SUFFIX))


def prepare_cases(args, tests_list, render_device, current_conf):

    baseline_path_tr = os.path.join(
        'c:/TestResources/usd_viewer_autotests_baselines', args.test_group)

    baseline_path = os.path.join(
        args.output_dir, os.path.pardir, os.path.pardir, os.path.pardir, 'Baseline', args.test_group)

    if not os.path.exists(baseline_path):
        os.makedirs(baseline_path)
        os.makedirs(os.path.join(baseline_path, 'Color'))

    for test in tests_list:
        report = RENDER_REPORT_BASE.copy()
        is_skipped = is_case_skipped(test, current_conf)
        test_status = TEST_IGNORE_STATUS if is_skipped else TEST_CRASH_STATUS

        main_logger.info("Case: {}; Skip here: {}; Predefined status: {};".format(
            test['name'], bool(is_skipped), test_status
        ))
        report.update({'test_status': test_status,
                       'render_device': render_device,
                       'test_case': test['name'],
                       'scene_name': test['scene_sub_path'],
                       'tool': 'USDViewer',
                       'file_name': test['name'] + test['file_ext'],
                       'script_info': test['script_info'],
                       'test_group': args.test_group,
                       'render_color_path': os.path.join('Color', test['name'] + test['file_ext']),
                       'width': test.get('width', 960),
                       'complexity': test.get('complexity', 'low'),
                       'colorCorrectionMode': test.get('colorCorrectionMode', 'sRGB'),
                       'renderer': test.get('renderer', ''),
                       'start_frame': test.get('start_frame', ''),
                       'end_frame': test.get('end_frame', ''),
                       'step': test.get('step', ''),
                       'camera': test.get('camera', ''),
                       'testcase_timeout': test['render_time']
                       })

        if 'Update' not in args.update_refs:
            # TODO move to jobs_launcher
            copy_baselines(test, baseline_path, baseline_path_tr)

        if test_status == TEST_IGNORE_STATUS:
            report.update({'group_timeout_exceeded': False})
            test['status'] = TEST_IGNORE_STATUS
        try:
            shutil.copyfile(
                os.path.join(ROOT_DIR_PATH, 'jobs_launcher', 'common', 'img', report['test_status'] + test['file_ext']),
                os.path.join(args.output_dir, 'Color', test['name'] + test['file_ext']))
        except (OSError, FileNotFoundError) as err:
            main_logger.error("Can't create img stub: {}".format(str(err)))

        with open(os.path.join(args.output_dir, test["name"] + CASE_REPORT_SUFFIX), "w") as file:
            json.dump([report], file, indent=4)


def generate_render_settings(args, test, target_dir):
    settings = []
    for key in test:
        if key in USDA_SETTINGS:
            settings.append("{type} {key} = \"{value}\"".format(type=USDA_SETTINGS[key]["type"], key=key, value=test[key]))
    if settings:
        main_logger.info("Detected USDA render settings")
        with open(os.path.join(os.path.dirname(__file__), "baseSettings.usda")) as file:
            render_settings = file.read()
        settings = ",\n        ".join(settings)
        render_settings = render_settings.format(settings=settings)
        if not os.path.exists(target_dir):
            os.makedirs(target_dir)
        settings_path = os.path.join(target_dir, "baseSettings.usda")
        if os.path.exists(settings_path):
            os.remove(settings_path)
        with open(os.path.join(target_dir, "baseSettings.usda"), "w") as file:
            file.write(render_settings)
        main_logger.info("File with USDA render settings was saved")
        return settings_path
    return ""


def merge_assets(args, test, work_dir, merged_scene_dir, render_settings_path):
    main_logger.info("Started merge scene and settings")
    scene_path = os.path.join(merged_scene_dir, "merged_scene.usda")
    if os.path.exists(scene_path):
        os.remove(scene_path)
    merge_script = "{usdstitch} {scene} {settings} --out {target}".format(usdstitch=args.tool.replace("usdrecord", "usdstitch"),
        scene=os.path.join(args.scene_path, test["scene_sub_path"]), settings=render_settings_path, target=scene_path)
    cmd_script_path = os.path.join(work_dir, "merge_script.bat")
    with open(cmd_script_path, "w") as f:
        f.write(merge_script)
    p = psutil.Popen(cmd_script_path, stdout=subprocess.PIPE, stderr=subprocess.PIPE, shell=True)
    stderr, stdout = b"", b""
    try:
        stdout, stderr = p.communicate(timeout=120)
    except (TimeoutError, psutil.TimeoutExpired, subprocess.TimeoutExpired) as err:
        main_logger.error("Merge of scene and settings was aborted by timeout")
        for child in reversed(p.children(recursive=True)):
            child.terminate()
        p.terminate()
        stdout, stderr = p.communicate()
        aborted_by_timeout = True

    with open(os.path.join(work_dir, "render_tool_logs", test["name"] + ".log"), "a") as file:
        file.write("-----[MERGE SCENE AND SETTINGS (USDSTITCH STDOUT)]------\n\n")
        file.write(stdout.decode("UTF-8"))
        file.write("\n-----[MERGE SCENE AND SETTINGS (USDSTITCH STDERR)]-----\n\n")
        file.write(stderr.decode("UTF-8"))
        file.write("\n\n")

    main_logger.info("Scene and settings were merged")

    return scene_path


def generate_command(args, test, work_dir):
    script_parts = [os.path.abspath(args.tool)]

    merged_scene_dir = os.path.join(args.scene_path, os.path.split(test["scene_sub_path"])[0])
    render_settings_path = generate_render_settings(args, test, merged_scene_dir)
    # check has current case render settings or not
    if render_settings_path:
        scene_path = merge_assets(args, test, work_dir, merged_scene_dir, render_settings_path)
        script_parts.append("--renderSettings \"/Render/PrimarySettings\"")
    else:
        scene_path = os.path.normpath(os.path.join(args.scene_path, test['scene_sub_path']))

    if "width" in test:
        script_parts.append("-w {}".format(test["width"]))
    if "complexity" in test:
        script_parts.append("-c {}".format(test["complexity"]))
    if "colorCorrectionMode" in test:
        script_parts.append("-color {}".format(test["colorCorrectionMode"]))
    if "renderer" in test:
        script_parts.append("-r {}".format(test["renderer"]))
    if "camera" in test:
        script_parts.append("-cam {}".format(test["camera"]))
    if "start_frame" in test:
        if "end_frame" in test:
            if "step" in test:
                script_parts.append("-f {}:{}x{}".format(test["start_frame"], test["end_frame"], test["step"]))
            else:
                script_parts.append("-f {}:{}".format(test["start_frame"], test["end_frame"]))
        else:
            script_parts.append("-f {}".format(test["start_frame"]))
    script_parts.append(scene_path)
    if "start_frame" in test or "end_frame" in test:
        key = "end_frame" if "end_frame" in test else "start_frame"
        target_image_name = os.path.join(work_dir, 
            "img{}.{}".format(str(math.floor(test[key])).rjust(5, "0"), str(test[key] % 1).ljust(5, "0")) + test["file_ext"])
        script_parts.append(os.path.join(work_dir, "img#####.#####" + test["file_ext"]))
    else:
        target_image_name = "img" + test["file_ext"]
        script_parts.append(os.path.join(work_dir, target_image_name))

    return " ".join(script_parts), target_image_name


def execute_cases(args, tests_list, test_cases_path, current_conf, work_dir):
    for test in [x for x in tests_list if x['status'] == 'active' and not is_case_skipped(x, current_conf)]:
        main_logger.info("Processing test case: {}".format(test['name']))

        error_messages = []
        test_case_prepared = False

        # build script for run current test case
        try:
            script, target_image_name = generate_command(args, test, work_dir)
            cmd_script_path = os.path.join(work_dir, "script.bat")
            with open(cmd_script_path, "w") as f:
                f.write(script)
            test_case_prepared = True
        except Exception as e:
            error_messages.append("Failed to prepare test case")
            main_logger.error("Failed to prepare test case. Exception: {}".format(str(e)))
            main_logger.error("Traceback: {}".format(traceback.format_exc()))

        i = 0
        render_time = -0.0
        test_case_status = TEST_CRASH_STATUS
        aborted_by_timeout = False
        while test_case_prepared and i < args.retries and test_case_status == TEST_CRASH_STATUS:
            main_logger.info("Try #" + str(i))
            i += 1

            p = psutil.Popen(cmd_script_path, stdout=subprocess.PIPE, stderr=subprocess.PIPE, shell=True)
            stderr, stdout = b"", b""
            start_time = time.time()
            test_case_status = TEST_CRASH_STATUS

            try:
                stdout, stderr = p.communicate(timeout=test["render_time"])
            except (TimeoutError, psutil.TimeoutExpired, subprocess.TimeoutExpired) as err:
                main_logger.error("Aborted by timeout. {}".format(str(err)))

                for child in reversed(p.children(recursive=True)):
                    child.terminate()
                p.terminate()
                stdout, stderr = p.communicate()
                aborted_by_timeout = True
            else:
                test_case_status = TEST_SUCCESS_STATUS

            render_time = time.time() - start_time
            try:
                target_path = os.path.join(args.output_dir, "Color", test["name"] + test["file_ext"])
                shutil.copyfile(os.path.join(work_dir, target_image_name), target_path)
                # check is image truncated or not
                output_image = Image.open(target_path)
                output_image.resize((64, 64), Image.ANTIALIAS)
                test_case_status = TEST_SUCCESS_STATUS
            except FileNotFoundError as err:
                image_not_found_str = "Image {} not found".format(os.path.basename(target_image_name))
                error_messages.append(image_not_found_str)
                main_logger.error(image_not_found_str)
                main_logger.error(str(err))
                test_case_status = TEST_CRASH_STATUS
            except OSError as err:
                if 'image file is truncated' in str(err):
                    file_is_truncated = "Output image is truncated"
                    error_messages.append(file_is_truncated)
                    main_logger.error(file_is_truncated)
                    main_logger.error(str(err))
                    test_case_status = TEST_DIFF_STATUS

            found_images = get_images_list(work_dir)

            with open(os.path.join(work_dir, "render_tool_logs", test["name"] + ".log"), 'a') as file:
                file.write("-----[TRY #{}]------\n\n".format(i - 1))
                file.write("-----[RENDER (USDRECORD STDOUT)]------\n\n")
                file.write(stdout.decode("UTF-8"))
                file.write("\n-----[FOUND IMAGES]-----\n")
                file.write(str(found_images))
                file.write("\n-----[RENDER (USDRECORD STDERR)]-----\n\n")
                file.write(stderr.decode("UTF-8"))
                file.write("\n\n")

            for img in found_images:
                try:
                    os.remove(os.path.join(work_dir, img))
                except OSError as err:
                    main_logger.error(str(err))

        # Read and update test case status
        with open(os.path.join(args.output_dir, test["name"] + CASE_REPORT_SUFFIX), "r") as file:
            test_case_report = json.loads(file.read())[0]
            if error_messages:
                test_case_report["message"] = test_case_report["message"] + error_messages
            test_case_report["test_status"] = test_case_status
            test_case_report["render_time"] = render_time
            test_case_report["render_log"] = os.path.join("render_tool_logs", test["name"] + ".log")
            test_case_report["group_timeout_exceeded"] = False
            test_case_report["testcase_timeout_exceeded"] = aborted_by_timeout
            test_case_report["testing_start"] = datetime.datetime.now().strftime("%m/%d/%Y %H:%M:%S")

        with open(os.path.join(args.output_dir, test["name"] + CASE_REPORT_SUFFIX), "w") as file:
            json.dump([test_case_report], file, indent=4)

        test["status"] = test_case_status
        with open(test_cases_path, "w") as file:
            json.dump(tests_list, file, indent=4)


def main():
    args = create_args_parser()

    work_dir = os.path.abspath(args.output_dir)

    if not os.path.exists(os.path.join(args.output_dir, "Color")):
        os.makedirs(os.path.join(args.output_dir, "Color"))
    if not os.path.exists(os.path.join(args.output_dir, "render_tool_logs")):
        os.makedirs(os.path.join(args.output_dir, "render_tool_logs"))

    try:
        test_cases_path = os.path.realpath(os.path.join(work_dir, 'test_cases.json'))
        shutil.copyfile(args.tests_list, test_cases_path)
    except Exception as e:
        main_logger.error("Can't copy test_cases.json")
        main_logger.error(str(e))
        exit(-1)

    try:
        with open(test_cases_path, 'r') as file:
            tests_list = json.load(file)
    except OSError as e:
        main_logger.error("Failed to read test cases json. ")
        main_logger.error(str(e))
        exit(-1)

    render_device = get_gpu()
    system_pl = platform.system()
    current_conf = set(platform.system()) if not render_device else {platform.system(), render_device}
    main_logger.info("Detected GPUs: {}".format(render_device))
    main_logger.info("PC conf: {}".format(current_conf))
    main_logger.info("Creating predefined errors json...")

    # save pre-defined reports with error status
    prepare_cases(args, tests_list, render_device, current_conf)

    with open(test_cases_path, 'w') as file:
        json.dump(tests_list, file, indent=4)

    # run cases
    execute_cases(args, tests_list, test_cases_path, current_conf, work_dir)

    return 0


if __name__ == "__main__":
    exit(main())