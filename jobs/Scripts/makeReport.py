import argparse
import os
import json


def generate_report(directory):
    files = os.listdir(directory)
    json_files = list(filter(lambda x: x.endswith('RPR.json'), files))
    result_json = []

    for json_file in json_files:
        with open(os.path.join(directory, json_file), 'r') as file:
            json_file_content = json.load(file)
            result_json.append(json_file_content[0])

    with open(os.path.join(directory, 'report.json'), 'w') as file:
        json.dump(result_json, file, indent=4)


def generate_renderTool_log(directory):
    files = os.listdir(os.path.join(directory, 'render_tool_logs'))
    log_files = list(filter(lambda x: x.endswith('.log'), files))
    render_tool_log = ''

    for log_file in log_files:
        with open(os.path.join(directory, 'render_tool_logs', log_file), 'r') as file:
            log_file_content = file.read()
            render_tool_log += "\n-----[FROM LOG '{}']-----\n".format(log_file)
            render_tool_log += log_file_content

    with open(os.path.join(directory, 'renderTool.log'), 'w') as file:
        file.write(render_tool_log)


if __name__ == "__main__":

    parser = argparse.ArgumentParser()
    parser.add_argument('--work_dir', required=True)
    args = parser.parse_args()

    generate_report(args.work_dir)
    generate_renderTool_log(args.work_dir)