import argparse
import os
import json


def generateReport(directory):
    files = os.listdir(directory)
    json_files = list(filter(lambda x: x.endswith('RPR.json'), files))
    result_json = []

    for json_file in json_files:
        with open(os.path.join(directory, json_file), 'w') as file:
            json_file_content = json.load(file)
            result_json.append(json_file_content)

    with open(os.path.join(directory, "report.json"), 'w') as file:
        json.dump(result_json, file, indent=4)


if __name__ == "__main__":

    parser = argparse.ArgumentParser()
    parser.add_argument('--work_dir', required=True)
    args = parser.parse_args()

    generateReport(args.work_dir)
