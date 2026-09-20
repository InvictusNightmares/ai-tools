# GPU sidecar smoke 与 candidate-r3 生命周期验证（仅隔离验证）

日期：2026-09-18。范围是GPU宿主上的共享网络命名空间sidecar连通性和采集器启停，不是4000/4001正式接入。

- 只读审计确认东京Nginx `tokyo-sub2api-proxy` 的原upstream为`106.14.254.110:9881`，美西`us-sub2api-proxy`为`106.14.254.110:9880`。
- sidecar分别在同一Nginx network namespace内监听`127.0.0.1:18400`和`127.0.0.1:18401`，采集关闭时转发根路径smoke返回200。
- 临时开启采集后，两地各记录1条`GET /`事件并成功写入；`dropped`、`truncated`、`write_errors`、`projection_errors`、`loss_persist_errors`均为0，随后关闭采集并移除临时sidecar。
- 随后将候选二进制放入GPU受限目录，由`work-observation-collector-candidate-r3@tokyo.service`和`@us.service`托管；两单元均`enabled/active`，执行一次`systemctl restart`后仍自动恢复。容器仍使用共享Nginx network namespace，18400/18401从Nginx容器内访问根路径均为200，重启后`capture_enabled=false`、`captured=0`、`written=0`，各错误/丢失计数为0。
- candidate-r3使用GPU实测存在的固定镜像`nginx@sha256:feb6f75a08aa55b44576f98c15b8859819ecf54f3e4d2157f42c2d01cb58a3d2`；候选启动脚本SHA为`e5f7de67688d2c2eb56d1cf79b73e291824a31c4d09f31a04fc94727724afc46`，systemd unit SHA为`ae21a8ed619c3120c19b76b15e097b6fa028e09ead2da0aa14b6f08834a78673`，候选二进制SHA为`7130a5d82f6e064e5c30ecd821f4a3a7af92e579824f24cb12a7d9a7399329d6`。GPU已创建并挂载统一200GiB ext4卷：镜像`/data/work-observation-volume-image/capture.ext4`，挂载点`/data/work-observation`，UUID `a3326109-6292-4556-a9a9-eac848858290`，`volume.py status` verified，可用约196GiB，挂载选项含`rw,nosuid,nodev,noexec`。candidate tokyo/us store 已迁移到该卷并完成服务启动状态核对；正式4000/4001仍未切换。
- 迁移后的卷上又完成一次受控sidecar smoke：两地临时开启采集，从原Nginx容器访问18400/18401均返回200，各新增1条事件，`captured=1/written=1`且所有损失/错误计数为0。`disable`为异步开关，等待约2秒后两地均为`capture_enabled=false`；随后重启两个systemd实例，仍为`active`，状态继续为关闭且事件存储量保持（Tokyo 9274 bytes、US 9262 bytes）。
- Tokyo短窗口首次真实切换在watchdog启动时暴露`access_log`字段缺陷；切换事务仍执行了disable和回退，原SHA恢复，未留下采集路由。修复并重新执行后，窗口时间为`2026-09-18T08:44:14Z`至`08:45:16Z`，请求60秒、12次采样、新增Nginx 5xx为0，`rollback_attempted=true`且`rollback_error=null`；最终原Nginx SHA保持不变、capture关闭、systemd active。窗口内只有采集器自检根路径事件，没有真实员工任务，因此p95仍只标记为post-check，不能当作性能验收。
- US随后完成同样的60秒短窗口（`08:47:04Z`至`08:48:07Z`、12次采样），新增Nginx 5xx为0，自动回退且`rollback_error=null`。最终Tokyo/US配置SHA分别保持`fe901328...fe756`和`7ed0ddff...01237`，两地`proxy_pass`仍指向原upstream，candidate systemd均active、capture均false；窗口同样只有自检事件，未形成真实员工p95样本。
- candidate unit的旧`ExecStop`权限失败已通过最小修复处理：原unit先备份，现改为`ExecStop=-/usr/bin/docker stop --time 30 ...`，unit SHA为`31b3831f197cf0bdaa9154e65f7178822b82a3df6a1ed047288678d8d266a5e1`；仅daemon-reload，未重启实例或改Nginx。
- 在短窗口演练后，按用户要求启动两地600秒观察窗口：state目录为`/data/work-observation/cutover-observe-20260918T085853Z`，Tokyo/US watchdog均运行118次采样并正常完成，`nginx_5xx=0`、`failure=null`、`rollback_error=null`、`rc=0`。两地manifest均为`rolled_back`，Nginx SHA恢复原值，sidecar仍由systemd active托管但`capture_enabled=false`；最终Tokyo `captured/written=3/3`、US `2/2`，各类损失/错误均为0。事件没有形成可验证的真实员工任务样本，p95仍需后续从真实工作事件离线复核。
- 4000/4001 Nginx配置全程保持原`proxy_pass`，没有真实员工请求经过采集器；实验目录中的正文证据不进入仓库。

4000/4001 Nginx配置SHA保持Tokyo `fe9013286c40a65d6e6530d7999913c427f76475a4c496f71e59ab16723fe756`、US `7ed0ddff41a89da3e23938ccd9b76d8defe83a36c0a8c107e19c798442501237`，原`proxy_pass`和上游均未改变。正式安装前仍需建立统一200GiB卷、生产状态/回退目录并完成短窗口演练；candidate-r3本身不代表入口已接入。
