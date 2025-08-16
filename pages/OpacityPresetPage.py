import os
import json
import shutil
import pygame
import live2d.v2 as live2d
import errno

from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QLabel, QPushButton, QFileDialog,
    QMessageBox, QListWidget, QListWidgetItem, QHBoxLayout, QTableWidget,
    QHeaderView, QTableWidgetItem, QCheckBox, QLineEdit, QComboBox
)
from PyQt5.QtCore import Qt

from sections.gen_jsonl import is_valid_live2d_json

PARTS_JSON_PATH = os.path.join("resource", "parts.json")


# ========= 通用工具 =========
def _ensure_dir(path: str):
    os.makedirs(path, exist_ok=True)

def _ensure_parent_dir(path: str):
    os.makedirs(os.path.dirname(path), exist_ok=True)

def _same_volume(src: str, dst: str) -> bool:
    """Windows: 比较盘符；POSIX: 比较 st_dev。"""
    try:
        src_drive = os.path.splitdrive(os.path.abspath(src))[0].lower()
        dst_drive = os.path.splitdrive(os.path.abspath(dst))[0].lower()
        if src_drive or dst_drive:
            return src_drive == dst_drive
    except Exception:
        pass
    try:
        return os.stat(os.path.abspath(src)).st_dev == os.stat(os.path.abspath(os.path.dirname(dst))).st_dev
    except Exception:
        return False

def _fsync_file(path: str):
    try:
        with open(path, 'rb') as f:
            os.fsync(f.fileno())
    except Exception:
        pass

def _fsync_dir(dir_path: str):
    try:
        if os.name == "nt":
            return
        fd = os.open(dir_path, os.O_DIRECTORY)
        try:
            os.fsync(fd)
        finally:
            os.close(fd)
    except Exception:
        pass

def _dedup_target_path(dst_path: str) -> str:
    """若目标重名，自动追加 _1/_2/..."""
    base = os.path.basename(dst_path)
    name, ext = os.path.splitext(base)
    folder = os.path.dirname(dst_path)
    final_dst = dst_path
    i = 1
    while os.path.exists(final_dst):
        final_dst = os.path.join(folder, f"{name}_{i}{ext}")
        i += 1
    return final_dst

def safe_move(src: str, dst: str) -> str:
    """
    可靠移动：
      - 先尝试 shutil.move
      - 跨盘或失败则 copy2 + fsync + unlink
      - 返回最终目标（含重名去重）
    """
    _ensure_parent_dir(dst)
    final_dst = _dedup_target_path(dst)

    try:
        shutil.move(src, final_dst)
        return final_dst
    except Exception as e:
        is_exdev = getattr(e, 'errno', None) == errno.EXDEV
        if is_exdev or not _same_volume(src, final_dst):
            try:
                shutil.copy2(src, final_dst)
                _fsync_file(final_dst)
                _fsync_dir(os.path.dirname(final_dst))
                os.unlink(src)
                _fsync_dir(os.path.dirname(src))
                return final_dst
            except Exception as e2:
                raise RuntimeError(f"跨盘复制删除失败：{src} -> {final_dst}, 错误: {e2}") from e2
        else:
            try:
                shutil.copy2(src, final_dst)
                _fsync_file(final_dst)
                _fsync_dir(os.path.dirname(final_dst))
                os.unlink(src)
                _fsync_dir(os.path.dirname(src))
                return final_dst
            except Exception as e3:
                raise RuntimeError(f"复制删除兜底失败：{src} -> {final_dst}, 错误: {e3}") from e3


# ========= 主页面 =========
# ========= 主页面 =========
class OpacityPresetPage(QWidget):
    def __init__(self):
        super().__init__()
        layout = QVBoxLayout(self)

        self.label = QLabel("选择文件夹后，自动列出所有合法的 model.json；逐行选择并套用预设")
        layout.addWidget(self.label)

        top_btn_layout = QHBoxLayout()
        self.select_btn = QPushButton("📁 选择文件夹")
        self.select_btn.clicked.connect(self.select_folder)
        top_btn_layout.addWidget(self.select_btn)

        # 来源子目录相关
        self.source_subdir_combo = QComboBox()
        self.source_subdir_combo.setEnabled(False)
        self.source_subdir_combo.setPlaceholderText("先选择根目录…")
        top_btn_layout.addWidget(self.source_subdir_combo)

        self.all_subdirs_checkbox = QCheckBox("遍历全部子目录")
        self.all_subdirs_checkbox.setChecked(False)
        self.all_subdirs_checkbox.toggled.connect(
            lambda checked: self.source_subdir_combo.setEnabled(not checked)
        )
        top_btn_layout.addWidget(self.all_subdirs_checkbox)

        # 复制/移动选择
        self.copy_mode_checkbox = QCheckBox("仅复制 .mtn/.exp.json（不删除源文件）")
        self.copy_mode_checkbox.setChecked(True)
        top_btn_layout.addWidget(self.copy_mode_checkbox)

        # 批量设为（作用于“勾选的行”）
        self.bulk_preset_combo = QComboBox()
        self.bulk_apply_btn = QPushButton("批量设为")
        self.bulk_apply_btn.clicked.connect(self.apply_bulk_preset_to_checked_rows)
        top_btn_layout.addWidget(self.bulk_preset_combo)
        top_btn_layout.addWidget(self.bulk_apply_btn)

        # 应用按钮
        self.apply_btn = QPushButton("应用所选预设")
        self.apply_btn.clicked.connect(self.apply_preset)
        top_btn_layout.addWidget(self.apply_btn)

        layout.addLayout(top_btn_layout)

        # 预设说明
        layout.addWidget(QLabel("提示：在下表中逐行选择预设；“保持不变”将跳过该行，“清空(全0)”会把所有部件设为0。"))

        # ✅ 表格：按行选择预设
        self.json_table = QTableWidget()
        self.json_table.setColumnCount(5)
        self.json_table.setHorizontalHeaderLabels(["✔", "model.json 路径", "检测到的预设", "选择预设", "预览"])
        self.json_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.Stretch)
        self.json_table.setColumnWidth(0, 44)
        self.json_table.setColumnWidth(2, 120)
        self.json_table.setColumnWidth(3, 160)
        self.json_table.setColumnWidth(4, 68)
        layout.addWidget(self.json_table)

        self.parts_data = {}
        self.root_dir = ""
        self.preset_names = []  # parts.json 的 key 列表（加载后填充）
        self.load_parts_json()

    def load_parts_json(self):
        if not os.path.exists(PARTS_JSON_PATH):
            QMessageBox.warning(self, "警告", f"未找到 parts.json：{PARTS_JSON_PATH}")
            return
        with open(PARTS_JSON_PATH, encoding="utf-8") as f:
            self.parts_data = json.load(f)

        # 预设下拉的可选项（顺序可按需调整）
        self.preset_names = list(self.parts_data.keys())
        specials = ["保持不变", "清空(全0)"]
        # 批量下拉
        self.bulk_preset_combo.clear()
        self.bulk_preset_combo.addItems(specials + self.preset_names)

    def _list_first_level_subdirs(self, base):
        try:
            return sorted(
                [d for d in os.listdir(base) if os.path.isdir(os.path.join(base, d))]
            )
        except Exception:
            return []

    def select_folder(self):
        folder = QFileDialog.getExistingDirectory(self, "选择模型文件夹")
        if not folder:
            return

        self.root_dir = folder
        self.label.setText(f"✅ 已选择：{folder}")
        self.json_table.setRowCount(0)

        # 填充来源子目录
        subdirs = self._list_first_level_subdirs(folder)
        self.source_subdir_combo.clear()
        if subdirs:
            self.source_subdir_combo.addItems(subdirs)
            self.source_subdir_combo.setEnabled(not self.all_subdirs_checkbox.isChecked())
        else:
            self.source_subdir_combo.setEnabled(False)

        # 枚举 model.json
        json_files = []
        def _collect_jsons(path, depth=0):
            if depth > 2:
                return
            try:
                for name in sorted(os.listdir(path)):
                    full = os.path.join(path, name)
                    if os.path.isdir(full):
                        _collect_jsons(full, depth + 1)
                    elif name.endswith(".json") and is_valid_live2d_json(full):
                        json_files.append(full)
            except Exception as e:
                print(f"❌ 错误: {e}")
        _collect_jsons(folder)

        # 填充表格（逐行可选预设）
        for i, path in enumerate(json_files):
            self.json_table.insertRow(i)

            # ✔ 是否处理
            checkbox = QCheckBox()
            checkbox.setChecked(True)
            self.json_table.setCellWidget(i, 0, checkbox)

            # 路径
            path_item = QTableWidgetItem(path)
            path_item.setFlags(Qt.ItemIsSelectable | Qt.ItemIsEnabled)
            self.json_table.setItem(i, 1, path_item)

            # 检测到的预设
            detected = self.detect_preset(path) or "无"
            detected_item = QTableWidgetItem(detected)
            detected_item.setFlags(Qt.ItemIsSelectable | Qt.ItemIsEnabled)
            self.json_table.setItem(i, 2, detected_item)

            # 选择预设（默认跟随“检测到的预设”，否则“保持不变”）
            preset_combo = QComboBox()
            options = ["保持不变", "清空(全0)"] + self.preset_names
            preset_combo.addItems(options)
            if detected in self.preset_names:
                preset_combo.setCurrentText(detected)
            else:
                preset_combo.setCurrentText("保持不变")
            self.json_table.setCellWidget(i, 3, preset_combo)

            # 预览按钮
            preview_btn = QPushButton("查看")
            preview_btn.clicked.connect(lambda _, row=i: self.preview_row_preset(row))
            self.json_table.setCellWidget(i, 4, preview_btn)

    def preview_row_preset(self, row: int):
        """弹窗展示该行 Combo 选中预设包含的部件数量/列表"""
        combo = self.json_table.cellWidget(row, 3)
        if not combo:
            return
        name = combo.currentText()
        if name == "保持不变":
            QMessageBox.information(self, "预览", "保持不变（不修改该 model.json 的 init_opacities）")
            return
        if name == "清空(全0)":
            QMessageBox.information(self, "预览", "清空：所有部件透明度置 0")
            return
        parts = self.parts_data.get(name, [])
        QMessageBox.information(
            self, "预览",
            f"预设：{name}\n包含 {len(parts)} 个部件ID：\n" + (", ".join(parts[:100]) + (" ..." if len(parts) > 100 else ""))
        )

    def detect_preset(self, json_path):
        try:
            with open(json_path, encoding="utf-8") as f:
                model = json.load(f)
            if "init_opacities" not in model:
                return "无"
            used_parts = [entry["id"] for entry in model["init_opacities"] if entry["value"] == 1.0]
            for category, parts in self.parts_data.items():
                if set(used_parts) == set(parts):
                    return category
            return "自定义"
        except Exception:
            return "未知"

    # 批量把 bulk_preset_combo 选中的预设，应用到“勾选的行”的“选择预设”下拉框
    def apply_bulk_preset_to_checked_rows(self):
        preset_name = self.bulk_preset_combo.currentText().strip()
        for row in range(self.json_table.rowCount()):
            cb = self.json_table.cellWidget(row, 0)
            if cb and cb.isChecked():
                combo = self.json_table.cellWidget(row, 3)
                if combo:
                    combo.setCurrentText(preset_name)
        QMessageBox.information(self, "完成", f"已将 {preset_name} 应用于勾选行的“选择预设”下拉。")

    def apply_preset(self):
        # 逐行处理
        traverse_all = self.all_subdirs_checkbox.isChecked()
        if not traverse_all:
            if self.source_subdir_combo.count() == 0:
                QMessageBox.warning(self, "警告", "未找到可用的来源子目录，请勾选“遍历全部子目录”或选择有子目录的根目录")
                return
            chosen_subdir = self.source_subdir_combo.currentText().strip()
            if not chosen_subdir:
                QMessageBox.warning(self, "警告", "请先选择来源子目录")
                return

        use_copy_only = self.copy_mode_checkbox.isChecked()

        updated = 0
        exported = 0
        skipped = 0

        # —— 写入各自预设
        for row in range(self.json_table.rowCount()):
            cb = self.json_table.cellWidget(row, 0)
            if not (cb and cb.isChecked()):
                continue

            path_item = self.json_table.item(row, 1)
            combo = self.json_table.cellWidget(row, 3)
            if not path_item or not combo:
                continue

            json_path = path_item.text()
            choice = combo.currentText().strip()

            if choice == "保持不变":
                continue

            try:
                all_parts = self.get_all_parts(json_path)
                if choice == "清空(全0)":
                    target_parts = set()
                else:
                    target_parts = set(self.parts_data.get(choice, []))

                init_opacities = [
                    {"id": pid, "value": 1.0 if pid in target_parts else 0.0}
                    for pid in all_parts
                ]

                with open(json_path, "r", encoding="utf-8") as f:
                    model_data = json.load(f)
                model_data.pop("motions", None)
                model_data.pop("expressions", None)
                model_data["init_opacities"] = init_opacities
                with open(json_path, "w", encoding="utf-8") as f:
                    json.dump(model_data, f, ensure_ascii=False, indent=2)
                updated += 1
            except Exception as e:
                print(f"❌ 处理失败: {json_path} 错误: {e}")

        # —— 集中动作/表情（与你原逻辑一致）
        try:
            if traverse_all:
                for dirpath, _, filenames in os.walk(self.root_dir):
                    for file in filenames:
                        low = file.lower()
                        if not (low.endswith(".mtn") or low.endswith(".exp.json")):
                            continue
                        src = os.path.join(dirpath, file)
                        rel = os.path.relpath(dirpath, self.root_dir)
                        top = rel.split(os.sep)[0] if rel != "." else "_root"
                        export_dir = os.path.join(self.root_dir, "expnmtn", top)
                        _ensure_dir(export_dir)
                        try:
                            if use_copy_only:
                                final_dst = _dedup_target_path(os.path.join(export_dir, file))
                                shutil.copy2(src, final_dst)
                                _fsync_file(final_dst); _fsync_dir(export_dir)
                            else:
                                _ = safe_move(src, os.path.join(export_dir, file))
                            exported += 1
                        except Exception as e:
                            print(f"❌ 集中失败：{src} -> {export_dir}，错误: {e}")
                            skipped += 1
            else:
                source_base = os.path.join(self.root_dir, chosen_subdir)
                if not os.path.isdir(source_base):
                    print(f"⚠️ 来源子目录不存在：{os.path.normpath(source_base)}")
                else:
                    export_dir = os.path.join(self.root_dir, "expnmtn", chosen_subdir)
                    _ensure_dir(export_dir)
                    for dirpath, _, filenames in os.walk(source_base):
                        for file in filenames:
                            low = file.lower()
                            if not (low.endswith(".mtn") or low.endswith(".exp.json")):
                                continue
                            src = os.path.join(dirpath, file)
                            try:
                                if use_copy_only:
                                    final_dst = _dedup_target_path(os.path.join(export_dir, file))
                                    shutil.copy2(src, final_dst)
                                    _fsync_file(final_dst); _fsync_dir(export_dir)
                                else:
                                    _ = safe_move(src, os.path.join(export_dir, file))
                                exported += 1
                            except Exception as e:
                                print(f"❌ 集中失败：{src} -> {export_dir}，错误: {e}")
                                skipped += 1
        except Exception as e:
            print(f"❌ 遍历错误：{e}")

        QMessageBox.information(
            self,
            "完成",
            f"已更新 init_opacities：{updated} 个\n"
            f"{'复制' if use_copy_only else '移动'}了 {exported} 个动作/表情到 expnmtn\\(按首层目录分组)\n"
            f"跳过/失败：{skipped}"
        )

    def get_all_parts(self, model_path):
        pygame.init()
        pygame.display.set_mode((1, 1), pygame.OPENGL | pygame.HIDDEN)
        live2d.init()
        live2d.glewInit()
        model = live2d.LAppModel()
        model.LoadModelJson(model_path)
        part_ids = model.GetPartIds()
        live2d.dispose()
        pygame.quit()
        return part_ids
