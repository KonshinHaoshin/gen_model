# 🎉 [gen_model](https://github.com/KonshinHaoshin/gen_model)

> 如果你觉得这个工具对你有帮助，欢迎关注 B 站 UP 主 **东山燃灯寺**！  
> 💖 你的支持是我持续改进的动力！  
> 🔗 B 站链接：[https://space.bilibili.com/296330875](https://space.bilibili.com/296330875?spm_id_from=333.1007.0.0)

✨ 本项目是一个专为 **Live2D Cubism 2 SDK 模型** 开发的资源管理与自动化工具，帮助用户轻松创建、更新并批量整理 `model.json` 配置文件，极大地减少手动编辑负担。

> ⚠️ 本工具**仅支持 Cubism 2 时代的模型结构**。

---

## 🔥 主要功能

### 1. ✅ 生成 `model.json`

- 自动扫描指定的 Live2D 模型目录，生成标准格式的 `model.json`。
- 自动分类并导入：
  - `.moc` 模型文件
  - `.physics.json` 物理配置
  - `.png` 贴图纹理
  - `.mtn` 动作
  - `.exp.json` 表情文件

### 2. ➕ 添加单个动作或表情

- 向已有的 `model.json` 添加单个 `.mtn` 或 `.exp.json` 文件。
- 自动路径相对化，方便跨平台使用。

### 3. 📦 批量添加动作或表情

- 支持输入一个文件夹或多个文件路径（用 `;` 分隔）进行批量导入。
- 可自定义名称前缀，便于组织管理。

### 4. 🧹 去重 + 删除无效路径（全新功能！）

- 自动检测并去重 `model.json` 中的重复动作/表情。
- 自动检测文件是否实际存在，**集中列出所有缺失项**，并询问是否一键删除对应记录。
- 自动备份原始 `model.json` 为 `.bak` 文件。

### 5. 🛠 批量修改 `.mtn` 文件中的 `PARAM_IMPORT` 参数

- 快速替换指定目录下所有 `.mtn` 文件中的 `PARAM_IMPORT` 值，用于调整动作权重或合成行为。

---

## 🚀 使用方法

1. **运行 `live2d_tool.py`**：

   ```bash
   python live2d_tool.py
   ```

2. **根据菜单提示选择功能**：

   ```
   1. 生成新的 model.json
   2. 添加单个动作/表情到 model.json
   3. 批量添加动作/表情到 model.json
   4. 去重 model.json 中重复的动作/表情，并删除不存在的路径
   5. 批量更改 mtn 文件中的 PARAM_IMPORT 参数
   q. 退出程序
   ```

3. **按照提示输入文件路径、参数等信息**，等待程序执行完成。

---

## 📂 推荐文件结构（示例）

```
your_model_folder/
├── model.moc
├── model.json
├── physics.json
├── texture_00.png
├── idle.mtn
├── happy.exp.json
└── ...
```

---

## 💡 小贴士

- 使用前请备份模型目录，避免误操作。
- 工具默认会对 `model.json` 进行 `.bak` 备份，放心修改。
- 建议在模型制作后期使用本工具进行资源整理与批量修复。

---

## 📜 License

本项目遵循 MIT 协议，欢迎自由使用、修改和分发。

---

如需自动化脚本、图形界面或与 Live2D Viewer 配套使用的功能，欢迎发起 Issue 或 PR！  
有更多想法也欢迎联系我，我会持续维护和优化。