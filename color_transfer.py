import os
from PIL import Image
import numpy as np
import matplotlib.pyplot as plt
import matplotlib
matplotlib.use('TkAgg')

def match_color(source: Image.Image, target: Image.Image) -> Image.Image:

    source_array = np.asarray(source).astype(np.float32)
    target_array = np.asarray(target).astype(np.float32)

    matched = np.zeros_like(source_array)
    for c in range(3):  # R, G, B
        src_mean, src_std = source_array[..., c].mean(), source_array[..., c].std()
        tgt_mean, tgt_std = target_array[..., c].mean(), target_array[..., c].std()
        src_std = max(src_std, 1e-6)
        matched[..., c] = (source_array[..., c] - src_mean) / src_std * tgt_std + tgt_mean
        matched[..., c] = np.clip(matched[..., c], 0, 255)

    return Image.fromarray(matched.astype(np.uint8))

def extract_webgal_rgb(source: Image.Image, target: Image.Image) -> dict:
    """
    对比源图与目标图的 RGB 平均亮度，生成 WebGAL 的 RGB 参数。
    每个 color 通道从默认 255 减去与源图的亮度差异。
    """
    source_array = np.asarray(source).astype(np.float32)
    target_array = np.asarray(target).astype(np.float32)

    webgal_rgb = {}
    for c, key in enumerate(["colorRed", "colorGreen", "colorBlue"]):
        src_mean = source_array[..., c].mean()
        tgt_mean = target_array[..., c].mean()

        # 模拟 WebGAL 从默认 255 削减亮度差（目标更暗，则数值更小）
        value = 255 - (src_mean - tgt_mean)
        webgal_rgb[key] = int(np.clip(value, 0, 255))

    return webgal_rgb


def visualize(source, target, matched):
    plt.figure(figsize=(15, 5))

    plt.subplot(1, 3, 1)
    plt.title("Source Image")
    plt.imshow(source)
    plt.axis("off")

    plt.subplot(1, 3, 2)
    plt.title("Reference Image")
    plt.imshow(target)
    plt.axis("off")

    plt.subplot(1, 3, 3)
    plt.title("Matched Result")
    plt.imshow(matched)
    plt.axis("off")

    plt.tight_layout()
    plt.show()

def main():
    print("制作者：东山燃灯寺")
    print("🎯 Please enter the path to the source image:")
    source_path = input("Source image path: ").strip().strip('"').strip("'")
    if not os.path.isfile(source_path):
        print("❌ File not found.")
        return
    source_img = Image.open(source_path).convert("RGB")

    png_dir = "png"
    if not os.path.isdir(png_dir):
        print(f"❌ Directory '{png_dir}' does not exist. Please create it and put reference images inside.")
        return

    candidates = [f for f in os.listdir(png_dir) if f.lower().endswith(".png")]
    if not candidates:
        print(f"❌ No PNG files found in '{png_dir}'.")
        return

    print("\n📂 Select a reference image:")
    for idx, name in enumerate(candidates):
        print(f"{idx+1}. {name}")
    index = int(input(f"Enter number (1 ~ {len(candidates)}): ").strip()) - 1
    if not (0 <= index < len(candidates)):
        print("❌ Invalid selection.")
        return

    target_path = os.path.join(png_dir, candidates[index])
    target_img = Image.open(target_path).convert("RGB").resize(source_img.size)

    matched_img = match_color(source_img, target_img)

    # 自动构造输出路径
    output_dir = "output"
    os.makedirs(output_dir, exist_ok=True)
    source_name = os.path.splitext(os.path.basename(source_path))[0]
    target_name = os.path.splitext(os.path.basename(target_path))[0]
    output_path = os.path.join(output_dir, f"matched_{source_name}_{target_name}.png")

    matched_img.save(output_path)
    print(f"\n✅ Color matching done. Saved to: {output_path}")

    # ✅ 输出 WebGAL 转换指令
    webgal_rgb = extract_webgal_rgb(source_img,target_img)
    webgal_code = f'setTransform:{webgal_rgb} -target=bg-main -duration=0 -next;'
    print("\n🎬 Suggested WebGAL Transform Command:")
    print(webgal_code)

    preview = input("📷 Preview result? (y/n): ").strip().lower()
    if preview.startswith("y"):
        visualize(source_img, target_img, matched_img)

if __name__ == "__main__":
    main()
