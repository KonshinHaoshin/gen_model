import os
import json


def sanitize_path(path):
    """去除路径两侧的引号，防止误识别"""
    return path.strip().strip('"')

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
        "physics": "",
        "textures": [],
        "motions": {},
        "expressions": []
    }

    for root, _, files in os.walk(directory):
        for file in files:
            relative_path = os.path.relpath(os.path.join(root, file), directory).replace("\\", "/")

            if file.endswith(".moc"):
                model_json["model"] = relative_path
            elif file.endswith(".physics.json"):
                model_json["physics"] = relative_path
            elif file.endswith(".png"):
                model_json["textures"].append(relative_path)
            elif file.endswith(".mtn"):
                motion_name = os.path.splitext(file)[0]
                model_json["motions"].setdefault(motion_name, []).append({"file": relative_path})
            elif file.endswith(".exp.json"):
                model_json["expressions"].append({"name": os.path.splitext(file)[0], "file": relative_path})

    return model_json

def update_model_json_bulk(model_json_path, new_files_or_dir):
    """批量更新 model.json，添加多个动作或表情"""
    model_json_path = sanitize_path(model_json_path)
    new_files_or_dir = sanitize_path(new_files_or_dir)

    if not os.path.exists(model_json_path):
        print("错误：model.json 文件不存在！")
        return

    with open(model_json_path, "r", encoding="utf-8") as f:
        model_data = json.load(f)

    # 计算相对路径的基准目录
    base_dir = os.path.dirname(model_json_path)

    # 如果输入是目录，则获取所有 .mtn 和 .exp.json 文件
    new_files = []
    if os.path.isdir(new_files_or_dir):
        for root, _, files in os.walk(new_files_or_dir):
            for file in files:
                if file.endswith((".mtn", ".exp.json")):
                    new_files.append(os.path.join(root, file))
    else:
        # 直接输入多个文件路径的情况
        new_files = new_files_or_dir.split(";")  # 允许用户用“;”分隔多个文件路径

    added_count = 0
    for new_file in new_files:
        new_file = sanitize_path(new_file)
        if not os.path.exists(new_file):
            print(f"警告：文件 {new_file} 不存在，跳过。")
            continue

        relative_path = os.path.relpath(new_file, base_dir).replace("\\", "/")
        file_name = os.path.basename(new_file)

        if file_name.endswith(".mtn"):
            motion_name = os.path.splitext(file_name)[0]
            model_data["motions"].setdefault(motion_name, []).append({"file": relative_path})
            print(f"添加动作: {relative_path}")
        elif file_name.endswith(".exp.json"):
            exp_name = os.path.splitext(file_name)[0]  # 去掉 `.exp.json`
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
                        print(f"在 {file_path} 中未找到参数 {param_name}")

                    # 将修改后的内容写回文件
                    with open(file_path, "w", encoding="utf-8") as f:
                        f.writelines(lines)

                except Exception as e:
                    print(f"处理 {file_path} 时出错: {e}")

if __name__ == "__main__":
    print("欢迎使用东山燃灯寺的live2d工具箱")
    print("具体教程请参考本人在B站上的视频")
    print("关注东山燃灯谢谢喵")
    print("1. 生成新的 model.json")
    print("2. 添加单个动作/表情到 model.json")
    print("3. 批量添加动作/表情到 model.json")
    # print("4. 其他特色功能")
    print("5. 批量更改mtn文件中的PARAM_IMPORT参数")
    choice = input("请选择操作 (1/2/3/4/5): ").strip()

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
        update_model_json_bulk(model_json_path, new_files_or_dir)
    # 后续会更新的（确信）
    # elif choice == "4":
    #     print("通过更改表情和动作文件实现断手断脚或一边没有眉毛")
    #     print("PS:立绘跟你是镜像的……别搞错了……")
    #     print("1. 左边没有眉毛")
    #     print("2. 右边没有眉毛")
    #     print("3. 失去左腿")
    #     print("4. 失去右腿")
    #     print("5. 失去左手")
    #     print("6. 失去右手")
    #     choice_new=input("请选择操作(1/2/3/4/5/6):").strip()
    elif choice == "5":
        directory = sanitize_path(input("请输入包含 .mtn 文件的目录路径: "))
        if not os.path.isdir(directory):
            print("错误：指定的路径不是一个目录或不存在。")
        else:
            new_value_str = input("请输入新的 PARAM_IMPORT 值（整数）: ")
            try:
                new_value = int(new_value_str)  # 确保新值是整数
                batch_update_mtn_param_text(directory, "PARAM_IMPORT", new_value)
            except ValueError:
                print("错误：请输入一个有效的整数值。")
    else:
        print("无效输入，请输入 1、2 或 3。")
