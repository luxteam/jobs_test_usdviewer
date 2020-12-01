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
from utils import is_case_skipped

ROOT_DIR_PATH = os.path.abspath(os.path.join(os.path.dirname(__file__), os.path.pardir, os.path.pardir))
sys.path.append(ROOT_DIR_PATH)
from jobs_launcher.core.config import *
from jobs_launcher.core.system_info import get_gpu


def create_args_parser():
    parser = argparse.ArgumentParser()
    parser.add_argument('--tests_list', required=True, metavar="<path>")
    parser.add_argument('--output_dir', required=True)
    parser.add_argument('--render_engine', required=True)
    parser.add_argument('--scene_path', required=True)
    parser.add_argument('--render_path', required=True, metavar="<path>")
    parser.add_argument('--test_group', required=True)
    parser.add_argument('--retries', required=False, default=2, type=int)
    parser.add_argument('--update_refs', required=True)
    # TODO: update list of params if it'll be necessary
    return parser.parse_args()


def main():
    args = create_args_parser()

    try:
        test_cases_path = os.path.realpath(os.path.join(os.path.abspath(args.output_dir), 'test_cases.json'))
        shutil.copyfile(args.tests_list, test_cases_path)
    except:
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

    if system_pl == "Windows":
        baseline_path_tr = os.path.join(
            'c:/TestResources/rpr_viewer_autotests_baselines', args.test_group)
    else:
        baseline_path_tr = os.path.expandvars(os.path.join(
            '$CIS_TOOLS/../TestResources/rpr_viewer_autotests_baselines', args.test_group))

    baseline_path = os.path.join(
        args.output_dir, os.path.pardir, os.path.pardir, os.path.pardir, 'Baseline', args.test_group)

    if not os.path.exists(baseline_path):
        os.makedirs(baseline_path)
        os.makedirs(os.path.join(baseline_path, 'Color'))

    # save pre-defined reports with error status
    for test in tests_list:
        report = core_config.RENDER_REPORT_BASE.copy()
        is_skipped = is_case_skipped(test, current_conf)
        test_status = TEST_IGNORE_STATUS if is_skipped else TEST_CRASH_STATUS

        main_logger.info("Case: {}; Engine: {}; Skip here: {}; Predefined status: {};".format(
            test['name'], engine, bool(is_skipped), test_status
        ))
        # TODO update pre-defined reports
        # TODO is testcase_timeout necessary
        # TODO is file_ext necessary
        # TODO source of engine
        report.update({'test_status': test_status,
                       'render_device': render_device,
                       'test_case': test['name'],
                       'scene_name': test['scene_sub_path'],
                       'tool': engine,
                       'file_name': test['name'] + test['file_ext'],
                       'date_time': datetime.datetime.now().strftime("%m/%d/%Y %H:%M:%S"),
                       'script_info': test['script_info'],
                       'test_group': args.test_group,
                       'render_color_path': 'Color/' + test['name'] + test['file_ext'],
                       'testcase_timeout': test['render_time']
                       })

        # TODO move to jobs_launacher
        if 'Update' not in args.update_refs:
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

    with open(test_cases_path, 'w') as file:
        json.dump(tests_list, file, indent=4)

    # run cases
    for test in [x for x in tests_list if x['status'] == 'active' and not is_case_skipped(x, current_conf)]:
        main_logger.info("\nProcessing test case: {}".format(test['name']))

        i = 0
        test_case_status = TEST_CRASH_STATUS
        while i < args.retries and test_case_status == TEST_CRASH_STATUS:
            main_logger.info("Try #" + str(i))
            i += 1
            # TODO implement configuration and running of each case
        # TODO implement saving of logs

        # Update test case status
        with open(os.path.join(args.output_dir, test['name'] + CASE_REPORT_SUFFIX), 'r') as file:
            test_case_report = json.loads(file.read())[0]
            # TODO Update info for test case

        with open(os.path.join(args.output_dir, test['name'] + CASE_REPORT_SUFFIX), 'w') as file:
            json.dump([test_case_report], file, indent=4)

        test["status"] = test_case_status
        with open(test_cases_path, 'w') as file:
            json.dump(tests_list, file, indent=4)

    return 0


if __name__ == "__main__":
    exit(main())