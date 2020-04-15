# -*- coding: utf-8 -*-

import json
import importlib
import os
import argparse

from .utils.misc import check_exist, get_dir

from pyretri.config import get_defaults_cfg
from pyretri.index import build_index_helper, feature_loader
from pyretri.evaluate import build_evaluate_helper


vgg_fea = ["pool5_PWA"]
res_fea = ["pool5_PWA"]


def load_datasets():
    datasets = {
        "oxford_gallery": {
            "gallery": "oxford_gallery",
            "query": "oxford_query",
            "train": "paris_all"
        },
        "cub_gallery": {
            "gallery": "cub_gallery",
            "query": "cub_query",
            "train": "cub_gallery"
        },
        "indoor_gallery": {
            "gallery": "indoor_gallery",
            "query": "indoor_query",
            "train": "indoor_gallery"
        },
        "caltech_gallery": {
            "gallery": "caltech_gallery",
            "query": "caltech_query",
            "train": "caltech_gallery"
        }
    }
    return datasets


def get_evaluate(fea_dir, evaluates):
    if "oxford" in fea_dir:
        evaluate = evaluates["oxford_overall"]
    else:
        evaluate = evaluates["overall"]
    return evaluate


def get_fea_names(fea_dir):
    if "vgg" in fea_dir:
        fea_names = vgg_fea
    else:
        fea_names = res_fea
    return fea_names


def parse_args():
    parser = argparse.ArgumentParser(description='A tool box for deep learning-based image retrieval')
    parser.add_argument('--fea_dir', '-fd', default=None, type=str, help="path of feature dirs", required=True)
    parser.add_argument("--search_modules", "-sm", default=None, type=str, help="name of search module's directory")
    parser.add_argument("--save_path", "-sp", default=None, type=str, help="path for saving results")
    args = parser.parse_args()

    return args


def main():
    # init args
    args = parse_args()
    assert args.fea_dir is not None, 'the feature directory must be provided!'
    assert args.search_modules is not None, 'the search modules must be provided!'
    assert args.save_path is not None, 'the save path must be provided!'

    # init retrieval pipeline settings
    cfg = get_defaults_cfg()

    # load search space
    datasets = load_datasets()
    queries = importlib.import_module("{}.query_dict".format(args.search_modules)).queries
    evaluates = importlib.import_module("{}.query_dict".format(args.search_modules)).evaluates

    if os.path.exists(args.save_path):
        with open(args.save_path, "r") as f:
            results = json.load(f)
    else:
        results = list()

    for dir in os.listdir(args.fea_dir):
        for data_name, data_args in datasets.items():
            for query_name, query_args in queries.items():
                if data_name in dir:
                    # get dirs
                    gallery_fea_dir, query_fea_dir, train_fea_dir = get_dir(args.fea_dir, dir, data_args)

                    # get evaluate setting
                    evaluate_args = get_evaluate(gallery_fea_dir, evaluates)

                    # get feature names
                    fea_names = get_fea_names(gallery_fea_dir)

                    for post_proc in query_args.post_processors.names:
                        if post_proc in ["PartPCA", "PartSVD", "PCA", "SVD"]:
                            query_args.post_processors[post_proc].train_fea_dir = train_fea_dir

                    for fea_name in fea_names:
                        result_dict = get_default_result_dict(dir, data_name, query_name, fea_name)
                        if check_exist(result_dict, results):
                            print("[Search Query]: config exists...")
                            continue

                        # load retrieval pipeline settings
                        query_args.feature_names = [fea_name]
                        cfg.index.merge_from_other_cfg(query_args)
                        cfg.evaluate.merge_from_other_cfg(evaluate_args)

                        # load features
                        query_fea, query_info, _ = feature_loader.load(query_fea_dir, [fea_name])
                        gallery_fea, gallery_info, _ = feature_loader.load(gallery_fea_dir, [fea_name])

                        # build helper and index features
                        query_helper = build_query_helper(cfg.query)
                        query_result_info, _, _ = query_helper.do_query(query_fea, query_info, gallery_fea)

                        # build helper and evaluate results
                        evaluate_helper = build_evaluate_helper(cfg.evaluate)
                        mAP, recall_at_k = evaluate_helper.do_eval(query_result_info, gallery_info)

                        # record results
                        to_save_recall = dict()
                        for k in recall_at_k:
                            to_save_recall[str(k)] = recall_at_k[k]
                        result_dict["mAP"] = float(mAP)
                        result_dict["recall_at_k"] = to_save_recall
                        results.append(result_dict)

                        # save results
                        with open(args.save_path, "w") as f:
                            json.dump(results, f)


if __name__ == '__main__':
    main()
