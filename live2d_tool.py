﻿import os
import json
from collections import defaultdict


def sanitize_path(path):
    """去除路径两侧的引号，防止误识别"""
    return path.strip().strip('"')

def remove_duplicates_and_check_files(model_json_path):
    with open(model_json_path, "r", encoding="utf-8") as f:
        model = json.load(f)

    base_dir = os.path.dirname(model_json_path)

    # 1️⃣ motions 去重并收集缺失文件
    new_motions = defaultdict(list)
    seen_motion_files = set()
    missing_motion_entries = []  # [(motion_name, motion_obj)]

    for motion_name, motion_list in model.get("motions", {}).items():
        for motion in motion_list:
            file_path = motion["file"]
            abs_path = os.path.join(base_dir, file_path)
            if file_path in seen_motion_files:
                print(f"⚠️ 跳过重复 motion: {file_path}")
                continue
            if not os.path.isfile(abs_path):
                missing_motion_entries.append((motion_name, motion))
            else:
                seen_motion_files.add(file_path)
                new_motions[motion_name].append(motion)

    # 2️⃣ expressions 去重并收集缺失文件
    seen_expression_files = set()
    new_expressions = []
    missing_expressions = []

    for expression in model.get("expressions", []):
        file_path = expression["file"]
        abs_path = os.path.join(base_dir, file_path)
        if file_path in seen_expression_files:
            print(f"⚠️ 跳过重复 expression: {file_path}")
            continue
        if not os.path.isfile(abs_path):
            missing_expressions.append(expression)
        else:
            seen_expression_files.add(file_path)
            new_expressions.append(expression)

    # 3️⃣ 一次性提示用户是否删除所有缺失项
    print("\n🧹 检测到缺失的动作和表情文件：")
    print(f"  - 缺失动作文件数：{len(missing_motion_entries)}")
    print(f"  - 缺失表情文件数：{len(missing_expressions)}")

    if missing_motion_entries or missing_expressions:
        confirm = input("是否删除以上所有丢失的动作/表情？(y/n): ").strip().lower()
        if confirm == "y":
            # 删除动作中缺失的部分
            for motion_name, motion in missing_motion_entries:
                print(f"🗑️ 删除 motion: {motion['file']}")
            # 重新组织 motion（不能直接加回去）
            new_motions_cleaned = defaultdict(list)
            for motion_name, motion_list in new_motions.items():
                new_motions_cleaned[motion_name].extend(motion_list)
            model["motions"] = new_motions_cleaned

            # 删除表情中缺失的部分
            for expression in missing_expressions:
                print(f"🗑️ 删除 expression: {expression['file']}")
            model["expressions"] = new_expressions
        else:
            # 用户不删除：仍保留原来不缺失的部分
            for motion_name, motion, in missing_motion_entries:
                new_motions[motion_name].append(motion)
            model["motions"] = new_motions
            model["expressions"] = new_expressions + missing_expressions
    else:
        print("✅ 未发现缺失的动作或表情文件。")

    # 保存备份并写入
    # backup_path = model_json_path + ".bak"
    # os.rename(model_json_path, backup_path)
    # print(f"📦 已备份原始文件为: {backup_path}")

    with open(model_json_path, "w", encoding="utf-8") as f:
        json.dump(model, f, ensure_ascii=False, indent=2)

    print("✅ 去重、缺失检查与保存完成！")

def scan_live2d_directory(directory):
    """遍历 Live2D 资源目录并生成 model.json"""
    model_json = {
        "version": "Sample 1.0.0",
        "layout": {"center_x": 0, "center_y": 0, "width": 2},
        "hit_areas_custom": {
            "head_x": [-0.25, 1], "head_y": [0.25, 0.2],
            "body_x": [-0.3, 0.2], "body_y": [0.3, -1.9]
        },
        "model": "",
        "textures": [],
        "motions": {},
        "expressions": []
    }

    physics_found = False

    for root, _, files in os.walk(directory):
        for file in files:
            relative_path = os.path.relpath(os.path.join(root, file), directory).replace("\\", "/")

            if file.endswith(".moc"):
                model_json["model"] = relative_path
            elif file.endswith(".physics.json"):
                model_json["physics"] = relative_path
                physics_found = True
            elif file.endswith(".png"):
                model_json["textures"].append(relative_path)
            elif file.endswith(".mtn"):
                motion_name = os.path.splitext(file)[0]
                model_json["motions"].setdefault(motion_name, []).append({"file": relative_path})
            elif file.endswith(".exp.json"):
                model_json["expressions"].append({"name": os.path.splitext(file)[0], "file": relative_path})

    # 如果没有找到 physics，则确保它不出现在最终 JSON 中
    if not physics_found and "physics" in model_json:
        del model_json["physics"]

    return model_json


def update_model_json_bulk(model_json_path, new_files_or_dir, prefix=""):
    """批量更新 model.json，添加多个动作或表情（支持添加前缀）"""
    model_json_path = sanitize_path(model_json_path)
    new_files_or_dir = sanitize_path(new_files_or_dir)

    if not os.path.exists(model_json_path):
        print("错误：model.json 文件不存在！")
        return

    with open(model_json_path, "r", encoding="utf-8") as f:
        model_data = json.load(f)

    base_dir = os.path.dirname(model_json_path)

    new_files = []
    if os.path.isdir(new_files_or_dir):
        for root, _, files in os.walk(new_files_or_dir):
            for file in files:
                if file.endswith((".mtn", ".exp.json")):
                    new_files.append(os.path.join(root, file))
    else:
        new_files = new_files_or_dir.split(";")

    added_count = 0
    for new_file in new_files:
        new_file = sanitize_path(new_file)
        if not os.path.exists(new_file):
            print(f"警告：文件 {new_file} 不存在，跳过。")
            continue

        relative_path = os.path.relpath(new_file, base_dir).replace("\\", "/")
        file_name = os.path.basename(new_file)

        if file_name.endswith(".mtn"):
            motion_name = prefix + os.path.splitext(file_name)[0]
            model_data["motions"].setdefault(motion_name, []).append({"file": relative_path})
            print(f"添加动作: {relative_path}（名称: {motion_name}）")
        elif file_name.endswith(".exp.json"):
            # 去除 `.exp.json` 后缀：先去 `.json` 再去 `.exp`
            exp_name = os.path.splitext(os.path.splitext(file_name)[0])[0]
            exp_name = prefix + exp_name
            model_data["expressions"].append({"name": exp_name, "file": relative_path})
            print(f"添加表情: {relative_path}（名称: {exp_name}）")
        else:
            print(f"跳过不支持的文件: {relative_path}")
            continue

        added_count += 1

    if added_count > 0:
        with open(model_json_path, "w", encoding="utf-8") as f:
            json.dump(model_data, f, indent=4, ensure_ascii=False)
        print(f"批量更新完成，共添加 {added_count} 个文件，已保存到 {model_json_path}")
    else:
        print("没有可添加的文件，未修改 model.json")


def batch_update_mtn_param_text(directory, param_name, new_value):
    """批量更新指定目录下所有 .mtn 文件中的指定参数值为新值（文本格式）"""
    for root, _, files in os.walk(directory):
        for file in files:
            if file.endswith(".mtn"):
                file_path = os.path.join(root, file)
                try:
                    # 读取文件所有行
                    with open(file_path, "r", encoding="utf-8") as f:
                        lines = f.readlines()

                    # 修改包含指定参数的行
                    modified = False
                    for i, line in enumerate(lines):
                        if line.strip().startswith(f"{param_name}="):
                            lines[i] = f"{param_name}={new_value}\n"
                            modified = True
                            print(f"已更新 {param_name} 在 {file_path} 为 {new_value}")
                            break

                    if not modified:
                        # 如果没有找到就添加
                        lines.append(f"{param_name}={new_value}\n")
                        print(f"未找到 {param_name}，已在 {file_path} 添加为 {new_value}")

                    # 写回文件
                    with open(file_path, "w", encoding="utf-8") as f:
                        f.writelines(lines)

                except Exception as e:
                    print(f"处理 {file_path} 时出错: {e}")


def main():
    while True:
        print("\n欢迎使用东山燃灯寺的live2d工具箱")
        print("具体教程请参考本人在B站上的视频")
        print("关注东山燃灯谢谢喵")
        print("1. 生成新的 model.json")
        print("2. 添加单个动作/表情到 model.json")
        print("3. 批量添加动作/表情到 model.json")
        print("4. 去重 model.json 中重复的动作/表情,并删除不存在的动作和表情路径")
        print("5. 批量更改 mtn 文件中的 PARAM_IMPORT 参数")
        print("q. 退出程序")
        choice = input("请选择操作 (1/2/3/4/5/q): ").strip()

        if choice == "1":
            directory = sanitize_path(input("请输入 Live2D 资源目录路径: "))
            save_path = os.path.join(directory, "model.json")
            model_data = scan_live2d_directory(directory)
            with open(save_path, "w", encoding="utf-8") as f:
                json.dump(model_data, f, indent=4, ensure_ascii=False)
            print(f"model.json 已生成: {save_path}")

        elif choice == "2":
            model_json_path = input("请输入 model.json 文件路径: ")
            new_file_path = input("请输入要添加的动作 (.mtn) 或表情 (.exp.json) 文件路径: ")
            update_model_json_bulk(model_json_path, new_file_path)

        elif choice == "3":
            model_json_path = input("请输入 model.json 文件路径: ")
            new_files_or_dir = input("请输入包含多个动作/表情的目录路径或多个文件（用 ; 分隔）: ")
            prefix = input("请输入添加到动作/表情名称前的前缀（可留空）: ").strip()
            update_model_json_bulk(model_json_path, new_files_or_dir, prefix=prefix)


        elif choice == "4":

            from collections import defaultdict


            path = input("请输入 model.json 的路径（例如 ./model3.json）：").strip().strip('"').strip("'")

            if not os.path.isfile(path):

                print("❌ 文件不存在，请检查路径是否正确。")

            else:

                remove_duplicates_and_check_files(path)



        elif choice == "5":
            directory = sanitize_path(input("请输入包含 .mtn 文件的目录路径: "))
            if not os.path.isdir(directory):
                print("错误：指定的路径不是一个目录或不存在。")
            else:
                new_value_str = input("请输入新的 PARAM_IMPORT 值（整数）: ")
                try:
                    new_value = int(new_value_str)
                    batch_update_mtn_param_text(directory, "PARAM_IMPORT", new_value)
                except ValueError:
                    print("错误：请输入一个有效的整数值。")

        elif choice.lower() == "q":
            print("感谢使用，再见喵~")
            break
        else:
            print("无效输入，请输入 1、2、3、5 或 q。")


if __name__ == "__main__":
    main()
