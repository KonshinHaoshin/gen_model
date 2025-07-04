import sys
import os
import json
from PyQt5.QtWidgets import (
    QApplication, QWidget, QPushButton, QLabel, QFileDialog,
    QVBoxLayout, QHBoxLayout, QMessageBox, QComboBox, QTextEdit,
    QGroupBox, QLineEdit, QFormLayout
)
from PyQt5.QtGui import QPixmap, QIcon
from PIL import Image
from live2d_tool import remove_duplicates_and_check_files, scan_live2d_directory, update_model_json_bulk, \
    batch_update_mtn_param_text
from color_transfer import match_color, extract_webgal_full_transform, visualize, plot_parameter_comparison
from gen_jsonl import collect_jsons_to_jsonl
CONFIG_PATH = "config.json"


class Float2Encoder(json.JSONEncoder):
    def iterencode(self, o, _one_shot=False):
        for s in super().iterencode(o, _one_shot=_one_shot):
            yield s.replace(".0,", ".00,").replace(".0}", ".00}")  # 保底小数位
            yield s


def format_transform_code(params: dict) -> str:
    def fmt(v):
        if isinstance(v, float):
            return round(v, 2)
        return v

    fixed = {k: fmt(v) for k, v in params.items()}
    rgb_only = {k: v for k, v in fixed.items() if k.startswith("color")}
    full_line = f'setTransform:{json.dumps(fixed, separators=(",", ":"), ensure_ascii=False)} -target=bg-main -duration=0 -next;'
    rgb_line = f'setTransform:{json.dumps(rgb_only, separators=(",", ":"), ensure_ascii=False)} -target=bg-main -duration=0 -next;'
    note = "⚠️ 完整参数匹配可能存在偏差，仅 RGB 值较为稳定"
    return f"{full_line}\n{rgb_line}\n{note}"



class ToolBox(QWidget):
    def __init__(self):
        super().__init__()
        # ✅ 设置图标（兼容打包后路径）
        if getattr(sys, 'frozen', False):
            base_path = sys._MEIPASS
        else:
            base_path = os.path.abspath(".")

        icon_path = os.path.join(base_path, "icon.png")
        if os.path.exists(icon_path):
            self.setWindowIcon(QIcon(icon_path))
        else:
            print("⚠️ icon.png 图标未找到！")
        self.setWindowTitle("Live2D 工具箱 - 东山燃灯")
        self.resize(900, 1200)  # 初始窗口大小
        self.setMinimumSize(700, 600)  # 可选：防止太小导致排版错乱

        self.source_path = ""
        self.target_path = ""
        self.result_path = ""

        layout = QVBoxLayout()
        layout.setSpacing(12)

        # 🎨 色彩匹配工具区域
        group_color = QGroupBox("🎨 色彩匹配工具")
        color_layout = QVBoxLayout()

        image_select_layout = QHBoxLayout()
        self.source_btn = QPushButton("选择源图像")
        self.source_btn.setMinimumWidth(160)
        self.source_btn.clicked.connect(self.choose_source)

        self.target_combo = QComboBox()
        self.target_combo.setMinimumWidth(160)
        self.refresh_target_list()
        self.target_combo.currentIndexChanged.connect(self.select_target_image)

        image_select_layout.addWidget(self.source_btn)
        image_select_layout.addWidget(self.target_combo)

        preview_layout = QHBoxLayout()
        self.source_label = QLabel("源图像")
        self.source_label.setFixedSize(220, 160)
        self.target_label = QLabel("参考图像")
        self.target_label.setFixedSize(220, 160)
        self.result_label = QLabel("匹配结果")
        self.result_label.setFixedSize(220, 160)

        self.compare_btn = QPushButton("显示对比图表")
        self.compare_btn.setMinimumWidth(300)
        self.compare_btn.clicked.connect(self.show_comparison)
        color_layout.addWidget(self.compare_btn)

        preview_layout.addWidget(self.source_label)
        preview_layout.addWidget(self.target_label)
        preview_layout.addWidget(self.result_label)

        self.match_btn = QPushButton("执行色彩匹配")
        self.match_btn.setMinimumWidth(300)
        self.match_btn.clicked.connect(self.run_match)

        self.webgal_output = QTextEdit()
        self.webgal_output.setPlaceholderText("此处将显示 WebGAL 指令...")
        self.webgal_output.setMinimumHeight(60)

        color_layout.addLayout(image_select_layout)
        color_layout.addLayout(preview_layout)
        color_layout.addWidget(self.match_btn)
        color_layout.addWidget(self.webgal_output)

        group_color.setLayout(color_layout)
        layout.addWidget(group_color)

        # 🧰 Live2D 工具区域
        group_l2d = QGroupBox("🧰 Live2D 工具部分")
        l2d_layout = QVBoxLayout()

        self.scan_btn = QPushButton("扫描目录并生成 model.json")
        self.scan_btn.setMinimumWidth(300)
        self.scan_btn.clicked.connect(self.generate_model_json)
        l2d_layout.addWidget(self.scan_btn)

        self.cleanup_btn = QPushButton("去重并清理 model.json")
        self.cleanup_btn.setMinimumWidth(300)
        self.cleanup_btn.clicked.connect(self.cleanup_model_json)
        l2d_layout.addWidget(self.cleanup_btn)

        # 📦 批量添加动作/表情
        group_batch_add = QGroupBox("📦 批量添加动作/表情")
        batch_layout = QFormLayout()

        self.batch_model_label = QLabel("未选择")
        btn_model = QPushButton("选择 model.json")
        btn_model.clicked.connect(self.select_batch_model_json)

        self.batch_file_label = QLabel("未选择")
        btn_file = QPushButton("选择动作/表情文件夹")
        btn_file.clicked.connect(self.select_batch_file_or_dir)

        self.prefix_input = QLineEdit()
        btn_add = QPushButton("执行添加")
        btn_add.clicked.connect(self.run_batch_add)

        batch_layout.addRow(btn_model, self.batch_model_label)
        batch_layout.addRow(btn_file, self.batch_file_label)
        batch_layout.addRow("前缀：", self.prefix_input)
        batch_layout.addRow("", btn_add)

        group_batch_add.setLayout(batch_layout)
        l2d_layout.addWidget(group_batch_add)

        # 🔧 批量修改 MTN 参数区域
        group_mtn_edit = QGroupBox("🔧 批量修改 MTN 文件参数")
        mtn_layout = QFormLayout()

        self.mtn_dir_label = QLabel("未选择")
        btn_select_mtn_dir = QPushButton("选择含 mtn 的文件夹")
        btn_select_mtn_dir.clicked.connect(self.select_mtn_directory)

        self.mtn_param_name_input = QLineEdit("PARAM_IMPORT")
        self.mtn_param_value_input = QLineEdit("30")

        btn_apply_mtn = QPushButton("批量更新")
        btn_apply_mtn.clicked.connect(self.run_mtn_batch_update)

        mtn_layout.addRow(btn_select_mtn_dir, self.mtn_dir_label)
        mtn_layout.addRow("参数名：", self.mtn_param_name_input)
        mtn_layout.addRow("新值：", self.mtn_param_value_input)
        mtn_layout.addRow("", btn_apply_mtn)

        group_mtn_edit.setLayout(mtn_layout)
        l2d_layout.addWidget(group_mtn_edit)

        group_l2d.setLayout(l2d_layout)
        layout.addWidget(group_l2d)

        # 📄 JSONL 生成区域
        group_jsonl = QGroupBox("📄 生成 JSONL 文件")
        jsonl_layout = QFormLayout()

        self.jsonl_root_label = QLabel("未选择")
        btn_select_root = QPushButton("选择根目录")
        btn_select_root.clicked.connect(self.select_jsonl_root)

        self.jsonl_prefix_input = QLineEdit("myid")
        btn_gen_jsonl = QPushButton("生成 JSONL")
        btn_gen_jsonl.clicked.connect(self.run_generate_jsonl)

        jsonl_layout.addRow(btn_select_root, self.jsonl_root_label)
        jsonl_layout.addRow("ID 前缀：", self.jsonl_prefix_input)
        jsonl_layout.addRow("", btn_gen_jsonl)

        group_jsonl.setLayout(jsonl_layout)
        layout.addWidget(group_jsonl)


        self.setLayout(layout)

        self.load_last_config()

    def show_comparison(self):
        try:
            if not hasattr(self, "_source_img") or not hasattr(self, "_target_img"):
                QMessageBox.warning(self, "未找到图像", "请先执行色彩匹配")
                return
            plot_parameter_comparison(self._source_img, self._target_img)
        except Exception as e:
            QMessageBox.critical(self, "出错", f"无法显示对比图：\n{str(e)}")

    def load_last_config(self):
        if os.path.exists(CONFIG_PATH):
            try:
                with open(CONFIG_PATH, "r", encoding="utf-8") as f:
                    config = json.load(f)

                # 色彩匹配路径
                self.source_path = config.get("color_match_source_path", "")
                if os.path.isfile(self.source_path):
                    self.source_label.setPixmap(QPixmap(self.source_path).scaled(200, 160))

                # Live2D 批量路径
                model_json_path = config.get("l2d_model_json_path", "")
                if os.path.isfile(model_json_path):
                    self.batch_model_json_path = model_json_path
                    self.batch_model_label.setText(model_json_path)

                file_or_dir = config.get("l2d_file_or_dir", "")
                if os.path.isdir(file_or_dir):
                    self.batch_file_or_dir = file_or_dir
                    self.batch_file_label.setText(file_or_dir)

                self.target_path = config.get("color_match_target_path", "")
                if os.path.isfile(self.target_path):
                    self.target_label.setPixmap(QPixmap(self.target_path).scaled(200, 160))

                jsonl_root_path = config.get("jsonl_root_path", "")
                if os.path.isdir(jsonl_root_path):
                    self.jsonl_root = jsonl_root_path
                    self.jsonl_root_label.setText(jsonl_root_path)

            except Exception as e:
                print("配置文件读取失败：", e)

    def save_config(self):
        config = {
            "color_match_source_path": self.source_path,
            "color_match_target_path": self.target_path,
            "l2d_model_json_path": getattr(self, "batch_model_json_path", ""),
            "l2d_file_or_dir": getattr(self, "batch_file_or_dir", ""),
            "jsonl_root_path": getattr(self, "jsonl_root", "")  # ✅ 新增
        }
        with open(CONFIG_PATH, "w", encoding="utf-8") as f:
            json.dump(config, f, indent=2, ensure_ascii=False)

    def refresh_target_list(self):
        png_dir = "png"
        self.target_combo.clear()
        if os.path.isdir(png_dir):
            files = [f for f in os.listdir(png_dir) if f.lower().endswith(".png")]
            self.target_combo.addItems(files or ["⚠ 无 PNG 文件"])
        else:
            self.target_combo.addItem("⚠ 缺少 png 文件夹")

    def select_target_image(self, index):
        if index < 0:
            return
        file_name = self.target_combo.itemText(index)
        path = os.path.join("png", file_name)
        if os.path.isfile(path):
            self.target_path = path
            self.target_label.setPixmap(QPixmap(path).scaled(200, 160))

    def choose_source(self):
        initial_dir = os.path.dirname(self.source_path) if self.source_path else ""
        file_path, _ = QFileDialog.getOpenFileName(self, "选择源图像", initial_dir, "Images (*.png *.jpg *.jpeg)")
        if file_path:
            self.source_path = file_path
            self.source_label.setPixmap(QPixmap(file_path).scaled(200, 160))
            self.save_config()

    def run_match(self):
        if not self.source_path or not self.target_path:
            QMessageBox.warning(self, "错误", "请先选择源图和参考图。")
            return

        source = Image.open(self.source_path).convert("RGB")
        target = Image.open(self.target_path).convert("RGB").resize(source.size)

        matched = match_color(source, target)
        source_dir = os.path.dirname(self.source_path)
        src = os.path.splitext(os.path.basename(self.source_path))[0]
        tgt = os.path.splitext(os.path.basename(self.target_path))[0]
        out_path = os.path.join(source_dir, f"matched_{src}_{tgt}.png")
        matched.save(out_path)

        self.result_path = out_path
        self.result_label.setPixmap(QPixmap(out_path).scaled(200, 160))

        webgal = extract_webgal_full_transform(source, target)
        self.webgal_output.setText(format_transform_code(webgal))
        QMessageBox.information(self, "完成", f"已保存匹配图像到：{out_path}")

        # 对比图
        self._source_img = source
        self._target_img = target
        self._matched_img = matched

    def generate_model_json(self):
        initial_dir = os.path.dirname(self.batch_model_json_path) if hasattr(self, "batch_model_json_path") else ""
        folder = QFileDialog.getExistingDirectory(self, "选择 Live2D 资源目录", initial_dir)
        if folder:
            data = scan_live2d_directory(folder)
            path = os.path.join(folder, "model.json")
            with open(path, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
            QMessageBox.information(self, "完成", f"已生成 model.json 到：{path}")

    def cleanup_model_json(self):
        initial_dir = os.path.dirname(self.batch_model_json_path) if hasattr(self, "batch_model_json_path") else ""
        path, _ = QFileDialog.getOpenFileName(self, "选择 model.json 文件", initial_dir, "JSON Files (*.json)")
        if path and os.path.isfile(path):
            remove_duplicates_and_check_files(path)
            QMessageBox.information(self, "完成", f"已完成清理：{path}")

    def select_batch_model_json(self):
        initial_dir = os.path.dirname(self.batch_model_json_path) if hasattr(self, "batch_model_json_path") else ""
        path, _ = QFileDialog.getOpenFileName(self, "选择 model.json 文件", initial_dir, "JSON Files (*.json)")
        if path:
            self.batch_model_json_path = path
            self.batch_model_label.setText(path)
            self.save_config()

    def select_batch_file_or_dir(self):
        initial_dir = self.batch_file_or_dir if hasattr(self, "batch_file_or_dir") else ""
        folder = QFileDialog.getExistingDirectory(self, "选择文件夹", initial_dir)
        if folder:
            self.batch_file_or_dir = folder
            self.batch_file_label.setText(folder)
            self.save_config()

    def run_batch_add(self):
        if not hasattr(self, "batch_model_json_path") or not hasattr(self, "batch_file_or_dir"):
            QMessageBox.warning(self, "⚠", "请先选择 model.json 和资源目录")
            return
        prefix = self.prefix_input.text()
        update_model_json_bulk(self.batch_model_json_path, self.batch_file_or_dir, prefix)
        QMessageBox.information(self, "完成", "批量添加完成！")

    def select_mtn_directory(self):
        initial_dir = self.mtn_dir if hasattr(self, "mtn_dir") else ""
        folder = QFileDialog.getExistingDirectory(self, "选择 MTN 文件夹", initial_dir)
        if folder:
            self.mtn_dir = folder
            self.mtn_dir_label.setText(folder)

    def run_mtn_batch_update(self):
        if not hasattr(self, "mtn_dir") or not os.path.isdir(self.mtn_dir):
            QMessageBox.warning(self, "⚠️", "请先选择 MTN 文件所在目录")
            return

        param_name = self.mtn_param_name_input.text().strip()
        try:
            new_value = int(self.mtn_param_value_input.text().strip())
        except ValueError:
            QMessageBox.warning(self, "⚠️", "请输入有效的整数值作为参数新值")
            return

        batch_update_mtn_param_text(self.mtn_dir, param_name, new_value)
        QMessageBox.information(self, "完成", f"已更新 {param_name} 为 {new_value}")


    # 生成拼好模所需的jsonl文件
    def run_generate_jsonl(self):
        if not hasattr(self, "jsonl_root"):
            QMessageBox.warning(self, "⚠️", "请先选择目录")
            return

        prefix = self.jsonl_prefix_input.text().strip()
        if not prefix:
            QMessageBox.warning(self, "⚠️", "请输入有效的 ID 前缀")
            return

        base_folder_name = os.path.basename(self.jsonl_root.rstrip(os.sep))
        output_path = os.path.join(self.jsonl_root, f"{base_folder_name}.jsonl")

        try:
            collect_jsons_to_jsonl(self.jsonl_root, output_path, prefix, base_folder_name)
            QMessageBox.information(self, "完成", f"JSONL 文件已生成：{output_path}")
        except Exception as e:
            QMessageBox.critical(self, "❌ 出错", f"生成失败：{str(e)}")

    def select_jsonl_root(self):
        folder = QFileDialog.getExistingDirectory(self, "选择用于生成 JSONL 的目录")
        if folder:
            self.jsonl_root = folder
            self.jsonl_root_label.setText(folder)
            self.save_config()  # ✅ 记住路径


if __name__ == "__main__":
    app = QApplication(sys.argv)
    if os.path.exists("style.qss"):
        with open("style.qss", "r", encoding="utf-8") as f:
            app.setStyleSheet(f.read())
    window = ToolBox()
    window.show()
    sys.exit(app.exec_())