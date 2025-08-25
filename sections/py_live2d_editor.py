import os
import pygame
import live2d.v2 as live2d

from utils.common import _norm_id


def get_all_parts(model_path):
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

def get_all_param_info_list(model_json_path):
    pygame.init()
    pygame.display.set_mode((1, 1), pygame.OPENGL | pygame.HIDDEN)
    live2d.init()
    live2d.glewInit()

    model = live2d.LAppModel()
    model.LoadModelJson(model_json_path)

    info_list = []
    try:
        count = model.GetParameterCount()
        for i in range(count):
            p = model.GetParameter(i)
            pid = _norm_id(getattr(p, "id", ""))
            pdefault = float(getattr(p, "default", 0.0) or 0.0)
            pmin = float(getattr(p, "min", 0.0) or 0.0)
            pmax = float(getattr(p, "max", 1.0) or 1.0)
            pvalue = float(getattr(p, "value", pdefault) or pdefault)

            info_list.append({
                "id": pid,
                "default": pdefault,
                "min": pmin,
                "max": pmax,
                "value": pvalue,
            })
    finally:
        # 先抽取完，再释放上下文
        live2d.dispose()
        pygame.quit()

    return info_list

def list_model_info(model_json_path):
    pygame.init()
    pygame.display.set_mode((1, 1), pygame.OPENGL | pygame.HIDDEN)
    live2d.init()
    live2d.glewInit()

    model = live2d.LAppModel()
    model.LoadModelJson(model_json_path)

    part_ids = model.GetPartIds()

    param_info_list = []
    for i in range(model.GetParameterCount()):
        param = model.GetParameter(i)
        param_info_list.append(param)  # 是 Parameter 类型，含 default/value/id 等

    live2d.dispose()
    pygame.quit()

    return part_ids, param_info_list



if __name__ == "__main__":
    user_input = input("请输入 model.json 的完整路径：\n> ")
    path = os.path.normpath(user_input.strip().strip('"').strip("'"))

    if not os.path.isfile(path):
        print("❌ 路径无效")
    else:
        parts, params = list_model_info(path)

        print("🧩 部件名列表：")
        for i, name in enumerate(parts):
            print(f"  {i+1}. {name}")

        print("\n🎛 参数名列表（含默认值）：")
        for i, param in enumerate(params):
            print(f"  {i+1}. {param.id} | 默认值: {param.default} | 当前值: {param.value}")