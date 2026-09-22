# 第三方资产来源与许可

本目录只存放**第三方**素材。自制资产在 `unreal/StarJourney/Content/Models`（导出的 glb）与 Blender 源工程。

## 采用（角色正式资产）

| 文件 | 来源 | 作者 | 许可 | 骨骼 | 片段 |
|---|---|---|---|---|---|
| `cc0/astronaut_space_suit.glb` | [poly.pizza](https://poly.pizza/m/3hC2i0CTuO) | Quaternius | **CC0** | 62 | 24（`Idle` `Run` `Run_Left` `Run_Right` `Walk` `Roll` `Kick_Left` `Kick_Right` …） |
| `cc0/fox_quaternius.glb` | [poly.pizza](https://poly.pizza/m/Bc97C66HKi) | Quaternius | **CC0** | 51 | 12（`Idle` `Idle_2` `Walk` `Gallop` `Gallop_Jump` …） |

**CC0 不要求署名**，也可以商用。这里仍然记录来源，是为了让资产**可追溯**：日后要换风格、要复核许可、要找回原始下载页时，不必重新搜索。

宇航员的 4 个蒙皮网格是 `SpaceSuit_Feet` / `SpaceSuit_Legs` / `SpaceSuit_Body` / `SpaceSuit_Head`，共用同一个 62 骨骨架。文件里另有一个 2 单位大的 `Icosphere` 网格，渲染中不可见，归一化时应排除。

## 已删除（曾被误标）

以下文件曾由一次自动检索加入，且**标注与实际内容不符**，已移除：

| 文件 | 曾被标注为 | 实际内容 |
|---|---|---|
| `astronaut_Quaternius_OgeSH89Nmx.glb` | 「宇航员，43 骨，含 `Duck`/`Jump`」 | 实际网格名 **`BarbaraTheBee`**，是一只卡通昆虫/蜜蜂（另带一个 `Pistol`） |
| `astronaut_Quaternius_zbtPq4dOJL.glb` | 「宇航员，同结构换色」 | 实际网格名 **`FernandoTheFlamingo`**，是一只火烈鸟 |
| `astronaut_PW-Wu_*.glb`、`astronaut_Poly-by-Google_*.glb` | 「宇航员候选」 | **CC-BY 3.0（有署名义务）**，且为静态网格、无骨骼无动画 |
| `astronaut_Polygonal-Mind_*.glb` ×3 | 「宇航员候选」 | 静态网格，包围盒仅 1–5 cm（小摆件） |
| 4 张搜索预览图（PNG） | — | 检索过程的对比图 |

> 教训：**资产的文件名不等于内容**。这三个「宇航员」文件里只有一个是真宇航员（`SpaceSuit_*`），另两个是动物。采用前**必须解析实际网格名并渲染确认**，不能只看文件名与提交信息。
>
> 注：被删除的文件仍存在于 git 历史中。彻底移除需重写历史，属破坏性操作，未执行。

## 复核方式

骨架数与**实际网格名**可直接解析验证，无需引擎：

```sh
python3 - <<'PY'
import json, struct, glob
for p in sorted(glob.glob('art/thirdparty/cc0/*.glb')):
    d = open(p,'rb').read(); off = 12
    while off < len(d):
        n, t = struct.unpack_from('<I4s', d, off); off += 8
        if t == b'JSON': js = json.loads(d[off:off+n])
        off += n
    names = [m.get('name') for m in js.get('meshes', [])]
    print(p, 'joints=', sum(len(s['joints']) for s in js.get('skins',[])),
          'clips=', len(js.get('animations',[])), 'meshes=', names)
PY
```
