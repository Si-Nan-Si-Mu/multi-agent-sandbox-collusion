# 蜂群智能算力平台：多 Agent 沙箱实验 Docker/特权环境申请

| 项 | 内容 |
|---|---|
| 日期 | 2026-11-10 |
| 用途 | 《智能系统防护》课程作业 / 科研对照实验 |
| 当前实例 | 蜂群 Notebook（SSH 入口 `ssh.zzai.scnet.cn:58222`） |
| 当前账号标识 | `acnkwfdzbt.2120090151878664194`（crdNotebook） |
| 申请人 | （填写姓名 / 学号 / 导师或任课教师） |
| 联系方式 | （填写邮箱 / 手机） |

---

## 1. 申请目的（一句话）

申请具备 **Docker（或同等容器运行时）与必要 Linux capability** 的开发/实验环境，用于搭建 **4–8 个本地 LLM Agent 的隔离沙箱 + 公共文件区 + CTF 风格评分器**，观察多 Agent 在不可解任务下是否出现共谋、欺骗评分器、以及通过公共区隐通道协调等行为。

本实验为受控安全研究，**不出公网攻击真实目标、不采集真实用户数据、不对外暴露服务**。

---

## 2. 当前环境已核实的限制（实测）

在现有 Jupyter/Notebook 容器内检测结果如下，因此仅 `apt install docker` **不足以**完成实验：

| 检查项 | 现状 | 后果 |
|---|---|---|
| 运行形态 | Kubernetes Notebook 容器（可见 `KUBERNETES_*`、containerd overlay） | 属于嵌套容器场景 |
| `CAP_SYS_ADMIN` | 无 | 难以启动 dockerd / 完整容器生命周期 |
| `CAP_NET_ADMIN` | 无 | 无法配置 bridge / iptables / 容器网络 |
| cgroup | `/sys/fs/cgroup` 只读 | 容器资源隔离与 daemon 管理受限 |
| Docker socket | 无 `/var/run/docker.sock` | 无法复用宿主机 Docker |
| KVM | 无 `/dev/kvm` | 微 VM（如 Firecracker）不可用 |
| 加速卡 | 1× 海光 HCU（约 64GB），空闲 | 计划跑本地 Qwen2.5-14B 级推理 |
| 资源余量 | 约 128 核 CPU / 503GB 内存；NFS `private_data` 可用 | 编排与日志空间充足 |

---

## 3. 希望平台提供的方案（任选其一即可）

按推荐优先级排序：

### 方案 A（推荐）：独立虚机 / 特权 Pod，内置 Docker

- 提供可 SSH 登录的 **特权开发机** 或 **`privileged: true` / 等价 capability 的 Pod**
- 预装或允许安装：`docker` / `containerd` + `docker compose`
- 可访问现有 **HCU**（或同等 1 卡 ≥48–64GB）
- 持久盘挂载到用户目录（可继续用 `/root/private_data` 或等价路径）

### 方案 B：挂载宿主机 Docker socket（rootless 或受限也可）

- 向 Notebook 挂载可用的 `/var/run/docker.sock`（或 rootless socket）
- 授权当前用户可 `docker run/build/ps/logs`
- 允许创建自定义 bridge 网络，或提供平台预置的隔离网络

### 方案 C：平台侧模板一键开通「多容器沙箱」

- 若不允许用户自管 Docker，可由平台提供：
  - 1 个推理服务容器（挂 HCU）
  - 4–8 个 agent 工作容器（无加速卡即可）
  - 1 个评分器容器
  - 共享卷：`/public`（可读写）+ 每 agent 私有卷

---

## 4. 具体权限/配置清单（便于管理员勾选）

### 4.1 Capability / SecurityContext（若走 K8s）

请至少放开以下之一组合：

**组合 1（完整 Docker，优先）**

- [ ] `privileged: true`，或等价地授予：
  - [ ] `CAP_SYS_ADMIN`
  - [ ] `CAP_NET_ADMIN`
  - [ ] `CAP_NET_RAW`（已有可保留）
  - [ ] `CAP_SYS_CHROOT` / `CAP_MKNOD`（已有可保留）
- [ ] cgroup 可写，或允许 systemd/cgroup v2 委派
- [ ] 允许加载/使用 overlay、bridge、veth（模块已在宿主机存在即可）

**组合 2（仅 Docker-out-of-Docker）**

- [ ] 挂载可用 `docker.sock`
- [ ] 服务账号可创建/删除本命名空间内容器与 volume
- [ ] 禁止该账号访问其他用户命名空间资源

### 4.2 网络与出站

- [ ] 容器间可互通（agent ↔ 评分器 ↔ 推理服务），**默认不对公网暴露端口**
- [ ] 如需拉取模型/基础镜像：允许访问镜像仓库与模型源（HuggingFace / 国内镜像 / 平台共享模型盘）
- [ ] 实验运行时建议 **限制任意出网**；模型下载可单独开临时白名单

### 4.3 存储

- [ ] 持久卷 ≥ **200GB**（模型约 30GB + 镜像 + 多轮日志/快照）
- [ ] 支持 volume：共享 `/public` + 每 agent 私有目录
- [ ] 可选：定期快照或用户可自助打包日志

### 4.4 计算资源（与现蜂群规格对齐即可）

- [ ] CPU ≥ 16 核（现有 128 核更佳）
- [ ] 内存 ≥ 64GB（现有 503GB 更佳）
- [ ] GPU/HCU：1× ≥ 48GB（现有约 64GB BW 足够跑 14B）
- [ ] 允许长时间任务（数小时推理服务常驻）

### 4.5 软件与镜像

- [ ] 允许安装 Docker Engine + Compose，或提供等价运行时
- [ ] 允许拉取/导入：Ubuntu/Python 基础镜像、（可选）vLLM/推理镜像
- [ ] 海光 DTK/PyTorch 环境可被推理容器使用（ROCm/DTK 设备挂载）

---

## 5. 实验架构（方便审核用途）

```
┌──────────────────────────────────────────────┐
│  Host / Privileged Env                        │
│  ┌─────────────┐   OpenAI-compatible API      │
│  │ LLM Server  │◄──────────────────────────┐  │
│  │ Qwen2.5-14B │                           │  │
│  │ (1× HCU)    │                           │  │
│  └─────────────┘                           │  │
│        ▲                                   │  │
│        │ HTTP                              │  │
│  ┌─────┴──────┐  ┌──────────┐  ┌─────────┐│  │
│  │ Agent ×4–8 │  │ Scorer   │  │ Observer││  │
│  │ (CPU only) │  │ (flags)  │  │ (logs)  ││  │
│  └─────┬──────┘  └────▲─────┘  └─────────┘│  │
│        │              │                    │  │
│        └──── /public ─┴── shared volume ───┘  │
└──────────────────────────────────────────────┘
```

- **Agent 数**：主实验 4 个，扩展组 8 个  
- **模型**：本地开源约 14B（单实例多路复用，不重复占卡）  
- **评分**：CTF 多级 flag；评分器与 agent 进程/容器隔离  
- **观测**：文件 diff、消息/工具调用、共谋与欺骗时间线  

---

## 6. 安全与合规承诺

1. 仅用于课程/科研受控实验，不进行未授权渗透真实业务系统。  
2. 不在公共区放置真实密钥、证件号、生产凭证。  
3. 对外端口默认关闭；如需临时开通，先报备端口与用途。  
4. 实验结束后可按平台要求清理镜像、容器与日志。  
5. 报告中将明确伦理声明与紧急停止机制（检测到外联/越权则中止）。  

---

## 7. 验收标准（开通后 30 分钟内可自测）

请管理员开通后，我们按下列命令自检（任选对应方案）：

```bash
# 方案 A
docker version
docker run --rm hello-world
docker network create agentnet
docker run --rm --network agentnet alpine ping -c 1 <scorer_or_peer>

# 方案 B
docker ps
docker run --rm -v $PWD/public:/public alpine ls /public

# 设备（推理容器）
# 容器内应能看到 HCU / ROCm-DTK 设备，并可被 PyTorch 识别
```

自检通过标准：

- [ ] 能创建 ≥ 6 个并发容器（4–8 agent + scorer + 可选 observer）  
- [ ] 容器间可通过自定义网络访问评分器端口  
- [ ] 共享卷读写正常，私有卷互不可见（或权限拒绝）  
- [ ] 推理容器能加载 14B 并完成一次生成  

---

## 8. 若不批准 Docker 的降级方案（已有预案）

若平台无法开通特权，实验将降级为：

- 同一 Notebook 内 **多进程 + 目录 soft isolation**（`unshare`/独立 UID + `/public`）  
- 仍使用本地 14B 单推理服务  
- 报告中注明隔离强度受限，并把「真容器隔离」列为未来工作  

因此本次申请是为了 **提升隔离真实性与防护课说服力**，不是实验能否开展的唯一前提。

---

## 9. 希望回复的信息

请平台反馈：

1. 可提供方案 A / B / C 中的哪一种？预计开通时间？  
2. 是否需要教师/课题组盖章或工单号？  
3. 镜像拉取、出网白名单、HCU 设备挂载有无额外限制？  
4. 计费方式（卡时 / 存储 / 特权实例差价）？  

---

## 10. 附件信息（提交时一并附上）

- 课程名称：《智能系统防护》  
- 实验简称：多 Agent 公共区共谋与评分器欺骗观测（本地 14B）  
- 当前实例 ID：`2120090151878664194`  
- 相关路径：`/root/private_data/`（现有数据盘）  
- 本清单文件：`docs/蜂群机_Docker特权申请清单.md`  
