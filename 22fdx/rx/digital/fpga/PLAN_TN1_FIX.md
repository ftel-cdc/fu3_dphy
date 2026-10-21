<!-- Bản lưu trong repo của plan đã được duyệt ngày 2026-10-19 (plan mode); nguồn: ~/.claude/plans/delightful-sleeping-hickey.md. -->

# Plan: sửa F1/F2 của ftel_dphy_rx để TN1 đạt hết, mốc ngang IP Xilinx (≥ 260 Mb/s) (2026-10-19)

> Repo `/home/linhhk/Documents/DPHY`, branch `dev`, sau commit `7e26771`.
> Ký hiệu: ✅ đã kiểm (đọc code, hoặc chạy thử trên bản copy RTL trong scratchpad) · ⚠️ ước lượng hoặc giả định · 🔍 kiểm khi làm.

## 0. Context

**Vì sao có plan này:**
- TN1 (commit `7e26771`): RX Xilinx đạt mọi kịch bản, còn `ftel_dphy_rx` hỏng do hai lỗi.
- Plan TN1–TN3 có quy định "sửa RTL cần plan riêng"; đây là plan đó.

**Bạn đã quyết (19/10):**
- Sửa trước. TN1 phải đạt hết rồi mới làm tiếp TN2 và TN3.
- Mốc là **ngang IP Xilinx**. Trên xcvp1902, Vivado chỉ cho IP Xilinx chạy 260–3200 Mb/s. Vì vậy không làm time-stamp DDR hay cắt ở mức bit để cắt đúng tới 80 Mb/s.

## 1. Nguyên nhân (đã kiểm)

| ID | Hiện tượng | Nguyên nhân | Bằng chứng |
|---|---|---|---|
| F2 | Mỗi burst, trên mỗi lane, có đúng một `rxvalidhs` nằm ngoài `rxactivehs`, mang byte sau trail | Ở `m_ftel_dphy_rx_sync_search.sv:242-248`, `valid = reg_locked && !w_detect` còn `active = i_start`. Ở chu kỳ `i_start` rơi, entry có valid = 1 và active = 0. `m_ftel_dphy_rx_eot.sv:179-191` đưa entry mới vào line mà không qua phép cắt. Vi phạm REQ-249 | Bản copy có thêm `&& i_start` ở 3 dòng thì hết lỗi ✅ |
| F1a | Cắt EoT lệch ở mọi rate khi dùng `eot_skip_bytes` của model | Công thức ở HAS Table 3-2, Appendix B và `Model.eot_skip` trong `config/validate_config.py` không trừ độ trễ đường dữ liệu: Λ + cửa sổ sync search + entry, khoảng 4–5 byte clock. Đây đúng là finding F-003 mà HAS đã ghi | Model cho 800/1440/1500 = 10/15/16. Cửa sổ đo được với trail min: ≤ 5 / ≤ 11 / ≤ 13 ✅ |
| F1b | Dưới khoảng 800 Mb/s, mất byte cuối với mọi giá trị skip. Ở 80 Mb/s mất 5–6 byte; burst từ 5 byte trở xuống mất hết | Sườn xuống của sync-search start tới Block No. 4 sau khoảng 2–3 byte clock, **sớm hơn** dữ liệu của cùng thời điểm (4–5 byte clock). Sync search xoá cửa sổ và lock ngay lúc đó, nên các byte đang trên đường bị mất; phép quét cũng chưa thấy đủ entry | Không có hold, ở 260 Mb/s chỉ skip 0 đúng, nằm sát mép ✅ |

**Không phải lỗi:** burst sát nhau ở 80 Mb/s.
- RTL không lỡ burst khi THS-EXIT + TLPX ≥ 315 ns; ràng buộc S5 của HAS là 415 ns, nên vẫn còn dư.
- E1-4a lỡ burst chỉ vì kịch bản dùng 225 ns ✅.

**Đính chính HAS:** mốc "cắt đúng trên khoảng 270 Mb/s" bỏ qua việc phép cắt đi theo từng byte.
- Để cắt đúng, cần ≥ 2 byte trail sạch, vì yêu cầu EoT có độ bất định 1 byte clock.
- Ở trường hợp xấu nhất HAS cho phép (THS-TRAIL min, nhiễu trong 40 ns trước LP-11), phải từ khoảng 600 Mb/s mới đủ 2 byte trail sạch.
- Ở 1440 Mb/s có 4 byte ⚠️. Đây là số tính tay; bước 2 sẽ đo lại.

## 2. Cách sửa (đã chạy thử trên bản copy ✅)

**RTL: Block No. 4, sửa 2 file:**
1. **`m_ftel_dphy_rx_hs_datapath.sv`: giữ burst mở thêm `C_EOT_HOLD_BYTES` = 3 byte clock** sau sườn xuống đã đồng bộ của sync-search start.
   - Sync search, cờ active và EoT request đều đi theo mức đã giữ. Nhờ vậy dữ liệu của lúc phát hiện LP-11 kịp vào delay line trước phép cắt.
   - EoT done gửi cho Block No. 3 vẫn ra ở sườn xuống chưa giữ. Vòng ADR-006 và S5 không đổi; thứ tự `stopstate_x` ở PPI cũng không đổi.
   - Nếu có sườn lên mới trong lúc giữ (chỉ xảy ra dưới 260 Mb/s với timing min), việc giữ kết thúc bằng một chu kỳ Low để hai burst không nhập vào nhau.
2. **`m_ftel_dphy_rx_sync_search.sv` (F2):** valid, sync và soterr thêm điều kiện `&& i_start`.

`m_ftel_dphy_rx_eot.sv` không đổi logic; chỉ sửa comment và tag nếu cần.

**Kết quả chạy thử** (chỉ RX mình, mô hình AFE hiện tại, trail min). Tiêu chí chặt: payload đúng **và** 0 byte trailer.

| Rate (Mb/s) | Không hold | Hold 2 | Hold 3 |
|---|---|---|---|
| 260 | skip {0}, sát mép | {1, 2} | {2, 3} |
| 800 | — | — | {3 … 8} (chưa dò dưới 3) |
| 1440 | — | — | {9 … 14} |
| 80 (ngoài phạm vi) | — | — | skip 0: payload nguyên, dư tối đa 1 byte trailer |

Với F2 đã sửa và skip nằm trong cửa sổ, E1-1…E1-3g, E1-4b và E1-4c đều cho 0 lỗi, 0 byte trailer ✅.

**Công thức và cấu hình:**
- `eot_skip_bytes` = (độ trễ phát hiện LP-11 + vượt CDC + hold − độ trễ đường dữ liệu + tâm cửa sổ cắt) / byte period.
- Các độ trễ lấy từ RTL. Hệ số chốt theo **giữa cửa sổ đo ở bước 2**, tức là đo có nhiễu và có jitter.
- Rate nào cửa sổ hẹp hơn 2 byte thì thiên về cắt muộn, để không bao giờ mất payload.
- File sửa:
  - `Model.eot_skip` và answer key trong `config/validate_config.py`;
  - giá trị reset trong `config/ftel_dphy_rx.yaml` (tại rate_ref);
  - sinh lại `logical/ftel_dphy_rx_config_pkg.sv`.

**HAS v0.16 (`doc/spec.md`):**
- **R1 giữ nguyên 80–1500 Mb/s.** Dải này còn xuất hiện ở K1, K8 và trong file gửi team CSI, nên không thu hẹp.
- **Ghi phạm vi bảo đảm của phép cắt trailer:**
  - từ 260 Mb/s: bảo đảm, ngang IP Xilinx trên Versal;
  - từ khoảng 600 Mb/s: đúng tới từng byte với mọi Tx đúng chuẩn;
  - 260–600 Mb/s: đúng với Tx thông thường; trường hợp xấu nhất (THS-TRAIL min + nhiễu) dư 1 byte trailer kèm EoT sync error, payload không mất;
  - dưới 260 Mb/s: không bảo đảm, chỉ ghi kết quả đo.
- **Các chỗ sửa:**
  - §4.6: thêm hold, mô tả lại thời điểm EoT done;
  - design note "EoT cut at low rates": đóng phần cắt; thứ tự stopstate vẫn OPEN ADR-006 với team CSI;
  - Table 3-2: công thức và giá trị reset của `eot_skip_bytes`;
  - Appendix B: dòng THS-SKIP;
  - `rxskewcalhs_x` rơi sau `rxactivehs_x` thêm một khoảng bằng hold;
  - chương 9: ADR-006; đóng F-003;
  - Figure 4-9: cả `.drawio` và `.svg`.
- **Quy trình như các bản trước:**
  1. đăng ký EXPECTED v0.16 trước trong `hw/utils/req_flow/spec_inventory.py`;
  2. sửa spec bằng script tái lập được, đặt trong scratchpad;
  3. resync P1: `rebase_req.py`, `/dphy_spec_parse` cho worklist, `assemble_req.py`, `validate_req.py`, rồi `flow_check.py --phase P1`;
  4. build docx v0.16 bằng `doc/md2docx.py` (python của anaconda) và chạy XSD validator.
- **`doc/sync/questions_csi_team.md` mục 2 (ADR-006):** thay con số "khoảng 270 Mb/s". Gửi hay không do bạn quyết.

**Flow RTL:**
- `check_rtl_rules.py`;
- `sim/vcs_lint.sh` cho 1, 2 và 4 lane;
- SpyGlass qua tool_flow;
- `flow_check.py --phase P2` và `--phase P3a`, 0 conflict; negatives 28/28;
- `doc/rtl_notes.md`: D-26 (hold), D-27 (F2), cập nhật lint log;
- sửa header các file RTL đã đổi;
- chạy lại B7 (`sim/tb_afe_adapter/run.sh`).

## 3. Bổ sung TN1 (`fpga/exp1`, `fpga/tools`)

- **`dphy_line_gen.sv` / `tb_exp1.sv`:**
  - `+EOT_JUNK=<ns>`: phần `<ns>` cuối của trail là bit ngẫu nhiên. Mô hình xấu nhất của HAS là 40 ns.
  - `+TRAIL_JITTER=1`: mỗi burst cộng thêm ngẫu nhiên 0–7 UI vào THS-TRAIL, để pha của LP-11 so với byte clock thay đổi. Hiện TN1 gần như giữ pha cố định, nên chưa thử hết độ bất định 1 byte clock.
- **`csi2_dump.py bursts`:** thêm `--max-trailer N` và báo lỗi khi vượt. RX mình dùng N = 0; riêng các hàng HAS cho phép thì N = 1. Selftest thêm ca vi phạm.
- **`run_exp1.sh`:**
  - build ở 260 Mb/s;
  - E1-4a chuyển sang 260 Mb/s, 4 lane, chạy cả hai RX, với timing mặc định và timing min (TRAIL/EXIT/LPX);
  - thêm **E1-5 (stress EoT)**, chạy stub, chỉ RX mình vì phép cắt là của RX mình: rate 260/400/600/800/1440/1500 × trail min/mặc định/max (TEOT) × có/không jitter × nhiễu 0/40 ns;
  - 80 Mb/s chạy stub chỉ để báo cáo, không tính đạt hay hỏng.

**Tiêu chí "TN1 đạt hết":**
- E1-1…E1-5 PASS cho cả hai RX:
  - payload đúng và đúng thứ tự;
  - `rxsynchs` đúng một lần mỗi burst;
  - không bật cờ lỗi;
  - không có `rxvalidhs` ngoài burst.
- RX mình: 0 byte trailer. Riêng hàng nhiễu 40 ns dưới khoảng 600 Mb/s được tối đa 1 byte, theo HAS v0.16.
- `run_exp1.sh summary` ra toàn PASS.

## 4. Thứ tự và ước lượng ⚠️

| Bước | Việc | Ước lượng |
|---|---|---|
| 1 | Lưu plan này vào `fpga/PLAN_TN1_FIX.md`; đăng ký EXPECTED v0.16 | 0,1 ngày |
| 2 | Bổ sung TN1 (mục 3); đo cửa sổ có nhiễu và jitter bằng bản RTL thử trong scratchpad ở 260/400/600/800/1440/1500 Mb/s, lấy số cho công thức | 0,5 ngày |
| 3 | HAS v0.16, resync P1, docx, file gửi team CSI | 0,5–1 ngày |
| 4 | Config, RTL, lint, P2/P3a, rtl_notes, B7 | 0,5 ngày |
| 5 | Chạy lại toàn bộ TN1; báo cáo; ghi chú vào README và PLAN_TN1_TN3; cập nhật memory | 0,5 ngày |

Tổng khoảng 2–2,5 ngày. Bước nào dài sẽ báo trước; build Vivado ở 260 Mb/s mất khoảng 5 phút.

## 5. Kiểm chứng

- **Selftest:** `csi2_dump.py` (thêm ca trailer vượt ngưỡng) và `validate_config.py` (answer key mới).
- **Biên của cửa sổ:**
  - ở rate nào HAS ghi "chính xác", cửa sổ đo được phải còn ≥ 1 byte biên ở mỗi phía;
  - ở 260 Mb/s, giá trị chọn phải nằm phía cắt muộn;
  - kiểm đối kháng bằng cách cố tình đặt skip lệch ±1 quanh giá trị chọn ở mỗi rate, xem biên có đúng như HAS ghi không.
- **RX Xilinx:** vẫn PASS ở mọi kịch bản cũ.
- **Flow:**
  - flow_check P1, P2, P3a: 0 conflict; negatives 28/28;
  - VCS và SpyGlass: 0/0/0;
  - B7: PASS.

## 6. Rủi ro và mục mở

- **Mô hình nhiễu EoT và độ trễ LP-RX của AFE đều là giả định.** Mô hình nhiễu lấy 40 ns. 🔍 Kiểm xem `questions_afe_team.md` đã hỏi về độ trễ LP-RX chưa.
- **Dư 1 byte trailer ở 260–600 Mb/s trong trường hợp xấu nhất.** Team CSI cần biết điều này; câu hỏi ADR-006 đã có sẵn.
- **Thứ tự `stopstate_x` / `rxactivehs_x`** (OPEN ADR-006): plan này không đổi.

## 7. Ngoài plan này

- Time-stamp DDR và cắt ở mức bit.
- Bảo đảm phép cắt dưới 260 Mb/s.
- Phương án "không chờ EoT done" của ADR-006.
- R2.
- Sửa `input logic` để XSIM không cần `--relax`; để sang TN2c.
- Commit: chỉ làm khi bạn bảo.

## 8. Độ tin cậy

- **HIGH:** nguyên nhân của F2, F1a và F1b (đã đọc code và chạy thử). Hold 3 cộng sửa F2 cho kết quả đúng ở 260, 800 và 1440 Mb/s với mô hình AFE hiện tại.
- **MED:** hệ số cuối cùng của công thức (chờ đo có nhiễu và jitter); mốc khoảng 600 Mb/s; ước lượng thời gian.
- **LOW:** hành vi của AFE thật ở EoT.

## 9. Kết quả (2026-10-20)

**Trạng thái:** đã làm xong. TN1 đạt hết: 113/113 kịch bản PASS cho cả hai RX (`fpga/exp1/run_exp1.sh summary`).
Chưa commit.

**Đã làm đúng như plan:**
- F2: `m_ftel_dphy_rx_sync_search.sv` thêm `&& i_start` cho valid, sync và soterr (D-27).
- F1: `m_ftel_dphy_rx_hs_datapath.sv` giữ sườn xuống 3 byte clock; EoT done vẫn ra ở sườn xuống chưa giữ (D-26).
- HAS v0.16; P1, P2, P3a 0 xung đột; test âm 28/28; VCS và SpyGlass sạch; B7 PASS; docx v0.16 XSD PASS.
- Bench: `+EOT_JUNK`, `+TRAIL_JITTER`, `+TRAIL=min|max`, `+SEED`; `csi2_dump.py --max-trailer`.
- E1-4a chạy ở 260 Mb/s (timing mặc định và timing min); thêm E1-5 (96 run) và báo cáo R-80.

**Khác với ước lượng của plan:**
- **Hằng số của công thức là 24 ns.**
  - Lần chạy lại đầu tiên còn 2 run E1-5 hỏng: dư byte trailer, payload vẫn nguyên.
  - Nguyên nhân: các lần đo trước giữ `core_clk` theo tỉ lệ cố định với đường truyền, nên LP-11 chỉ gặp vài pha.
  - Bench thêm `+CORE_HALF=2.501` (`core_clk` chậm 400 ppm, trôi qua mọi pha) và target `run_exp1.sh window`. Target
    này quét `eot_skip_bytes` từ giá trị model − 1 tới + 2, mỗi ô 1120 burst, bảng in bằng `eot_window.py`.
  - Kết quả: hằng số cũ 27 ns không còn biên 1 byte ở 600, 800 và 1440 Mb/s, vì giá trị + 1 đã mất payload trong
    1–7 / 1120 burst.
  - Đổi sang 24 ns theo luật của mục 2 (thiên về cắt muộn). Giá trị: 600 → 4, 800 → 6, 1440 → 13. Các rate khác và
    giá trị reset (14) không đổi.
  - Đo lại: + 1 không mất payload ở rate nào; + 2 mất ở mọi rate.
- **Phạm vi cắt trailer (HAS Table 4-7) kém hơn ước lượng "dư tối đa 1 byte":**
  - không nhiễu: chính xác từ 600 Mb/s; ở 260 Mb/s 13 % số burst còn trailer, ở 400 Mb/s 0,9 %;
  - có 40 ns nhiễu: 99 % số burst ở 260–400 Mb/s; 0,3–3 % từ 1000 Mb/s; 1,2 % ở 1440 Mb/s; 0 ở 1500 Mb/s;
  - mỗi burst còn tối đa ⌊(THS-TRAIL + 29 ns) / byte period⌋ − `eot_skip_bytes` byte, tính tại TEOT,max: 4 byte ở
    260 Mb/s, 12 byte ở 1440 và 1500 Mb/s.

  Vẫn ngang hoặc hơn IP Xilinx: IP này giữ nguyên trailer ở mọi burst (2 byte ở 260 Mb/s, 9 ở 800, 16–18 ở 1440/1500).
- **Tiêu chí của mục 3 sửa theo HAS:**
  - Không nhiễu: RX mình 0 byte trailer từ 600 Mb/s.
  - Các trường hợp còn lại: tối đa bằng cột cuối của Table 4-7 (hàm `tmax` trong `run_exp1.sh`).

**Kết quả TN1 (lần chạy cuối):**

| Kịch bản | Byte trailer: RX Xilinx | Byte trailer: `ftel_dphy_rx` | Kết quả |
|---|---|---|---|
| E1-1, E1-2a–c, E1-3a–g, E1-4d/e (1440 Mb/s) | 14–17 | 0 | PASS |
| E1-4a (260 Mb/s, timing mặc định / min) | 1–2 | 0 / 0–2 | PASS |
| E1-4b, E1-4c (800, 1500 Mb/s) | 9, 17–18 | 0 | PASS |
| E1-5 (96 run, chỉ RX mình) | — | trong Table 4-7; lớn nhất 12, ở 1440 Mb/s có nhiễu | PASS |
| R-80 (ngoài phạm vi, chỉ báo cáo) | — | 0–1 ở 10/36 burst; payload nguyên | — |

**Còn mở:**
- ADR-006: thứ tự `stopstate_x` / `rxactivehs_x`, và việc controller CSI-2 có bỏ qua byte trailer sau footer không.
  Câu 2 trong `doc/sync/questions_csi_team.md` đã cập nhật số; gửi hay không do bạn quyết.
- Hành vi thật của AFE ở EoT (độ trễ LP-RX so với HS-RX, đầu ra HS-RX sau LP-11) vẫn là giả định (ADR-001).

**Độ tin cậy:**
- HIGH: payload không mất và biên 1 byte, đo trên RTL với mọi pha.
- MED: số trailer tối đa (công thức khớp mọi số đo, nhưng hằng số 29 ns là số khớp từ đo).
- LOW: AFE thật.
