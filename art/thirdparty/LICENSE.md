# 第三方资产来源与许可

本目录只存放**第三方**素材。自制资产在 `art/source/`（Blender 源）与 `content/Models`（导出的自制 glb）。

## 采用（角色正式资产）

| 文件 | 来源 | 作者 | 许可 | 骨骼 | 片段 |
|---|---|---|---|---|---|
| `cc0/astronaut_quaternius.glb` | [poly.pizza](https://poly.pizza/m/OgeSH89Nmx) | Quaternius | **CC0** | 43 | 18（含 `Duck` `Jump` `Idle` `Run` `Walk`） |
| `cc0/fox_quaternius.glb` | [poly.pizza](https://poly.pizza/m/Bc97C66HKi) | Quaternius | **CC0** | 51 | 12（含 `Idle` `Gallop`） |

**CC0 不要求署名**，也可以商用。这里仍然记录来源，是为了让资产**可追溯**：日后要换风格、要复核许可、要找回原始下载页时，不必重新搜索。

## 备用

| 文件 | 用途 | 许可 |
|---|---|---|
| `cc0/astronaut_quaternius_variant.glb` | 与宇航员同结构、不同配色；M1 阶段渲染对比后**二选一**，落选者删除 | CC0 |
| `cc0/astronaut_directional_clips.glb` | 含 `Run_Left`/`Run_Right`/`Kick_Left`/`Kick_Right` 等定向片段。骨架为 248 骨（与主用 43 骨不同），**当前方案不依赖它**，仅在未来需要重定向时备用 | CC0 |

## 已删除

以下曾由一次自动检索加入，已移除：

- `astronaut_PW-Wu_*.glb`、`astronaut_Poly-by-Google_*.glb` —— **CC-BY 3.0，有署名义务**；且两者都是**静态网格、无骨骼无动画**，无法承担角色动画。采用 CC0 路线后它们没有任何用途。
- `astronaut_Polygonal-Mind_*.glb` ×3 —— CC0，但为静态网格，包围盒仅 1–5 cm（小摆件尺寸），与本项目角色无关。
- 4 张搜索用预览图（PNG）。

> 注：这些文件仍存在于 git 历史中。若要彻底移除需要重写历史，属于破坏性操作，未执行。

## 复核方式

`glb` 的骨架数与片段名可直接解析验证，无需引擎：

```sh
python3 - <<'PY'
import json, struct, glob
for p in sorted(glob.glob('art/thirdparty/cc0/*.glb')):
    d = open(p,'rb').read()
    off = 12
    while off < len(d):
        n, t = struct.unpack_from('<I4s', d, off); off += 8
        if t == b'JSON': js = json.loads(d[off:off+n])
        off += n
    print(p, 'joints=', sum(len(s['joints']) for s in js.get('skins',[])),
          'clips=', len(js.get('animations',[])))
PY
```
