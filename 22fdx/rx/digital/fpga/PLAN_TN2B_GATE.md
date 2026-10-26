# Plan: phương án A — khối chỉnh PPI ở FPGA cho controller CSI-2 của AMD (2026-10-26)

> Repo `fu3_dphy`, branch `dev`, sau commit `e456f21`; thư mục `22fdx/rx/digital/fpga/`.
> Ký hiệu: ✅ đã kiểm · ⚠️ ước lượng hoặc giả định · 🔍 kiểm khi làm.
> Làm sau [`PLAN_CHECK_C6_C10.md`](PLAN_CHECK_C6_C10.md), để lần chạy lại TN2b dùng checker mới. Duyệt ngày 2026-10-26.

## 0. Context

- **Vấn đề** (TN2b, [`PLAN_TN2B.md`](PLAN_TN2B.md) §14–15): controller CSI-2 RX SS 6.0 của AMD, bản không PHY, không nhận packet nào từ `ftel_dphy_rx`.
  - `ftel_dphy_rx` nâng `rxactivehs` 7–20 byte clock trước `rxsynchs`.
  - Controller của AMD cần hai tín hiệu này lên cùng lúc.
  - Khi testbench giữ `rxactivehs` tới `rxsynchs` (`+PPI_AMD_TIMING=3`), cả 27 run dương đều PASS.
- **Quyết định (2026-10-23):** chọn **phương án A**: một khối chỉ ở FPGA, đặt giữa `ftel_dphy_rx` và RX SS không PHY. RTL ASIC (`logical/`, `config/`), HAS và hợp đồng với controller CSI-2 giữ nguyên.
- **Hiện trạng:** việc chỉnh mới chỉ là code TB ([`exp2b/tb_exp2b.sv`](exp2b/tb_exp2b.sv), phần `+PPI_AMD_TIMING`).
  - Code đó viết theo kiểu TB: dùng giá trị đầu thay cho reset, và chung chỗ với các mode chẩn đoán.
  - Nó có một lỗ: hai burst chỉ cách nhau một cycle thì burst sau lọt `rxactivehs` sớm. HAS §4.6 cho phép trường hợp này dưới 260 Mb/s khi THS-EXIT ở mức min; TN2b chưa gặp.
- **Kết quả muốn có:**
  - một khối RTL tổng hợp được, viết theo [`../doc/rtl_rule.md`](../doc/rtl_rule.md);
  - được kiểm riêng, rồi kiểm trong TN2b thay cho code TB;
  - được ghi vào đặc tả TN3 để team FPGA dùng.

## 1. Bản ghi quyết định (A/B/C, 2026-10-23)

**Dữ kiện:**

| # | Dữ kiện | Nguồn |
|---|---|---|
| F1 | Controller AMD cần khoảng `rxactivehs` → `rxsynchs` = 0. Khoảng 0 thì PASS; 7, 12, 19–20 thì ra 0 packet; 1–6 chưa thử | ✅ TN2b, các run DBG |
| F2 | Khoảng của ftel ≥ 3 ở mọi capture đã lưu: 3–4 ở 80 Mb/s, 8–9 ở 1440 với THS-PREPARE/ZERO min, 19–20 với TX của AMD. D-PHY AMD luôn bằng 0 | ✅ capture TN1, TN2a |
| F3 | Ví dụ PPI (phần informative) của spec D-PHY vẽ `RxActiveHS` lên cùng `RxSyncHS`, byte đầu ở cycle sau, tức là kiểu AMD | ✅ |
| F4 | Controller CSI-2 của team CSI, theo bảng Burst FSM và quy tắc cờ trong HAS của họ, cần `rxactivehs` lên trước `rxsynchs` ít nhất 1 byte clock. Hình ví dụ trong chính HAS đó lại vẽ hai tín hiệu lên cùng lúc, nên cần team CSI xác nhận | ⚠️ suy từ văn bản, chưa có RTL của họ |
| F5 | Suy ra: không có một hành vi duy nhất nào của ftel hợp với cả hai controller. Hành vi hiện tại hợp với controller CSI | từ F1, F2, F4 |

**Các phương án:**
- **A:** khối chỉnh ở FPGA.
- **B:** tham số tổng hợp trong ftel.
- **C0:** convention khoảng 0; team CSI phải sửa FSM.
- **C1:** convention khoảng đúng 1; chỉ dùng được nếu AMD nhận khoảng 1.

**Kết quả chấm điểm:**
- **Cổng loại:** chỉ A và B qua đủ. C0 bắt team CSI phải sửa; C1 cần một thí nghiệm chưa làm.
- **Ma trận** (cách chấm của HAS §7: điểm 1–5 × trọng số, tối đa 120): **A 102**, B 88, C1 74, C0 64.
- **Thứ tự giữ nguyên** ở profile "ưu tiên dùng lại IP" (A 108 / B 101 / C1 83 / C0 77 trên 135) và "ưu tiên prototype sớm" (121 / 102 / 87 / 73 trên 140).
- **Khi gộp các tiêu chí tương quan:** vẫn A > B > C1 > C0.
- **B chỉ vượt A** khi giá trị lâu dài nặng gấp hơn ~2,4 lần chi phí và rủi ro.
- **Ảnh hưởng của A tới các team khác:** team CSI không có; team FPGA (TN3) thêm một khối do nhóm D-PHY giao; AFE và phía TX không có.
- **Có thể lật kết quả:** câu trả lời của team CSI cho F4. Nếu họ coi "`rxactivehs` từ byte hợp lệ đầu tiên" là bắt buộc, chip cũng phải sửa RTL. Chuyện này không thuộc plan này.
- **Plan này tốn ~1,5 ngày, nhiều hơn mức ~1 ngày dùng trong ma trận**, vì có thêm unit TB, synth và E2b-9. A vẫn đứng đầu: K3 từ 5 xuống 4, tổng còn 100.

## 2. Khối `m_ftel_ppi_act_gate` (`fpga/rtl/`)

**Chức năng, từng lane:**
- `o_rxactivehs = i_rxactivehs & (i_rxsynchs | reg_seen)`.
- `reg_seen` = 1 khi có `i_rxsynchs` trong lúc `i_rxactivehs` = 1, và về 0 khi `i_rxactivehs` = 0.
- Không thêm trễ. Mỗi lane 1 flop và 1–2 cổng, thêm 2 flop của reset sync.
- Các tín hiệu PPI khác đi thẳng từ ftel vào RX SS, không qua khối.

**Port** (rtl_rule N2, N5, N11, F5):

| Port | Ghi chú |
|---|---|
| `PARA_NUM_LANES` | 1, 2, 4 |
| `i_byte_clk` | `rxbyteclkhs` của `ftel_dphy_rx` |
| `i_byte_rst_n` | Active-low, bất đồng bộ; nối cùng reset với `ftel_dphy_rx`. Đồng bộ bên trong bằng `m_ftel_dphy_rx_rst_sync` (cell của `logical/`), có tag `CDC_CROSSING` (K3, K4, K5) |
| `i_rxactivehs`, `i_rxsynchs` `[PARA_NUM_LANES-1:0]` | PPI của ftel, sau phần gating `dl_enable` của ftel |
| `o_rxactivehs` `[PARA_NUM_LANES-1:0]` | Vào `dlN_rxactivehs` của RX SS |

**Hành vi theo từng trường hợp:**

| Trường hợp | Ra |
|---|---|
| Burst thường | Lên cùng `rxsynchs` (khoảng 0, như D-PHY AMD); xuống cùng `rxactivehs` của ftel, EoT không đổi |
| Leader lỗi 1 bit (`errsoths`) | Vẫn có `rxsynchs`, nên như burst thường |
| Lỗi sync (HAS C8: `errsotsynchs`, không có `rxsynchs`) | `rxactivehs` giữ 0 suốt burst. `errsotsynchs` đi thẳng. ⚠️ Chưa biết D-PHY AMD làm gì trong trường hợp này, nên E2b-9 cho xem controller phản ứng ra sao |
| Burst deskew (không có `rxsynchs`) | Giữ 0. Không dùng ở ≤ 1,5 Gb/s (rate của TN3) |
| Hai burst cách nhau 1 cycle (HAS §4.6) | `reg_seen` về 0 ở cycle nghỉ, nên burst sau cũng chờ sync của nó |
| Byte clock dừng | Giữ trạng thái; đầu ra theo đầu vào (như E2b-8) |
| Reset | Xoá bất đồng bộ; nhả sau 2 byte clock |

**Tên:**
- Không dùng tiền tố `m_ftel_dphy_rx_*`, vì tiền tố đó dành cho IP trong `logical/`, và checker profile `ip` bắt theo nó.
- Áp mọi luật [M] về tên và code bằng tay, rồi kiểm bằng `req_flow/check_rtl_rules.py --profile construct` cùng lint VCS L1.

**File:**
- `rtl/m_ftel_ppi_act_gate.sv`;
- `rtl/tb_m_ftel_ppi_act_gate.sv`;
- `rtl/run_rtl.sh`, với các lệnh `lint | rules | sim | synth | all`;
- `rtl/synth_rtl.tcl`.

Output đặt ở `work/rtl/` (đã gitignore).

## 3. Kiểm khối riêng

- **Unit TB (VCS), theo mẫu của `sim/tb_afe_adapter/`:**
  - TB có model riêng, viết độc lập theo §2, và so với khối ở mọi byte clock.
  - Kích thích cho từng lane, ngẫu nhiên kèm có hướng:
    - khoảng sync từ 0 đến 25;
    - burst không có sync, kèm `errsotsynchs`;
    - nghỉ 1 cycle giữa hai burst;
    - reset giữa burst;
    - clock dừng giữa burst.
  - Chạy với NL = 1, 2, 4.
  - Mọi bộ đếm coverage phải > 0; TB in `TB RESULT: PASS`.
- **Lint L1:** `vcs -full64 -sverilog +lint=all,noVCDE` với NL = 1, 2, 4, phải ra 0 Error / Warning / Lint.
- **Luật:** `check_rtl_rules.py --profile construct` phải ra 0 vi phạm.
- **Synth:** Vivado 2025.2 out-of-context trên `xcvp1902-vsva6865-2MP-e-S`, NL = 4, clock 224 MHz (envelope 1792/8). Báo:
  - utilization, kỳ vọng 6 FF;
  - WNS ≥ 0;
  - `report_methodology`;
  - `report_cdc`.

  Đây không phải sign-off của thiết kế FPGA; sign-off thuộc TN3.

## 4. Đưa vào TN2b

**`exp2b/tb_exp2b.sv`:**
- **`+PPI_ADAPTER=1`:** `rxactivehs` vào `xrxss_np` lấy từ instance `u_act_gate`.
  - Đầu vào của `u_act_gate` là PPI của ftel sau `+PPI_CORRUPT`.
  - Data, valid, sync và các tín hiệu lỗi đi thẳng.
  - Không dùng chung với `+PPI_AMD_TIMING`; dùng chung thì `$fatal`.
  - Các mode 1/2/3 và `+PPI_XFILL` giữ nguyên, vì là các run của phát hiện.
- **Checker:** TB có model riêng, so với khối ở mọi byte clock và in `TB ADAPTER CHECK: comparisons N, differences D`.
- **`+PPI_SOTSYNCERR=<lane>,<packet>`:**
  - Ở burst đó của lane đó, `rxsynchs` và `rxvalidhs` trước khối thành 0, và `errsotsynchs` pulse một lần ở chỗ `rxsynchs` lẽ ra xuất hiện.
  - Đó là mẫu ftel ra theo HAS C8. Vị trí của pulse là gần đúng ⚠️, nhưng không ảnh hưởng khối hay controller, vì `rxactivehs` vẫn 0.
  - Kết thúc run: chờ R-X đủ line, rồi `drain_quiet` cho R-F.

**Script:**
- `exp2b.tcl` compile thêm `rtl/m_ftel_ppi_act_gate.sv`.
- `sources()` của `run_exp2b.sh` và `sources_hash()` của `tn2b_evidence.py` thêm file đó.
- `run_exp2b.sh`:
  - `shim` dùng `+PPI_ADAPTER=1`, vẫn giữ tag `SH_`;
  - kịch bản mới **E2b-9**: 1440 Mb/s, 4 lane, 3 frame 640×16, `+PPI_SOTSYNCERR=0,5` (lane 0, packet 5 = line 4 của frame 0). E2b-9 nằm trong `all`, không nằm trong `model`.

**`tn2b_evidence.py`:**
- `tbcheck`: mục `adapter`. Ở mọi run `SH_*`, comparisons phải > 0 và differences = 0.
- **Check mới `gate`, xét riêng E2b-9:**
  - R-X PASS;
  - frame 1 và 2 của R-F trùng golden từng pixel (phục hồi), `TB DONE OK` (không treo);
  - trong `ftel_ppi.csv`, burst của lane 0 ở packet 5 không có `rxactivehs` và có một `errsotsynchs`;
  - các số còn lại chỉ báo cáo.
- `evselftest`: thêm lỗi cài: adapter có 1 difference; frame 1 của E2b-9 lệch 1 pixel; burst bị hỏng có `rxactivehs`.

**Chạy lại:**
- chép 39 run sang `work/exp2b/_pre_gate/` (~450 MB, không xoá gì);
- build lại 4 rate, chạy `shim` (31 run) và `finding` (9);
- so hồi quy: CSV và `frames.txt` của 39 run trùng từng byte với bản cũ.

## 5. Docs

- **`exp3/TN3_SPEC.md`:** sơ đồ R-F có khối chỉnh; §0 thêm một dòng ghi rằng nhóm D-PHY giao file khối và nối nó ở đâu. Không dùng ID nội bộ.
- **`exp2b/README.md`:** khối và plusarg; E2b-9; quyết định A; số đo của lần chạy lại; check `adapter`/`gate`; lệnh.
- **`PLAN_TN2B.md`:** một dòng trỏ sang plan này.
- **`fpga/README.md`** và memory.
- **Không đổi:** `logical/`, `config/`, `doc/spec.md`, `exp1/*.sv`, `exp2/*.sv`.

## 6. Bước, cổng, ước lượng ⚠️

| Bước | Việc | Cổng: sai thì dừng và báo | Ước lượng |
|---|---|---|---|
| 2a | Khối, unit TB, lint, luật, synth | Unit PASS; lint 0; luật 0; WNS ≥ 0. Cảnh báo do cell reset sync của ASIC thiếu `ASYNC_REG` thì chỉ báo: ftel dùng cùng cell đó, và việc map cell sang FPGA thuộc TN2c | 0,4 ngày |
| 2b | TB, script, evidence; chạy SH_E2b-1 và E2b-9 | SH_E2b-1 PASS với 0 difference, CSV trùng bản cũ. Ở E2b-9, nếu controller treo hoặc không phục hồi thì dừng: quy tắc cho burst lỗi sync cần được quyết | 0,4 ngày |
| 2c | Chạy lại TN2b (~45 phút máy), evidence, evselftest, so hồi quy | Evidence PASS mọi check; evselftest bắt đủ; CSV trùng từng byte | 0,3 ngày |
| 2d | Đặc tả TN3, docs, memory | Quét token ra 0 | 0,25 ngày |

Commit chỉ khi được bảo.

## 7. Rủi ro

1. **CSV không trùng từng byte** vì thứ tự event của XSIM đổi khi có module mới. Khi đó so theo nội dung. Nếu khác ngoài X hoặc thời gian thì dừng và báo.
2. **Controller AMD xử lý mẫu E2b-9 sai**: treo hoặc lệch các packet sau. Khi đó dừng, báo, và đưa ra quy tắc thay thế: nâng `rxactivehs` cùng `errsotsynchs`.
3. **`report_methodology` / `report_cdc` cảnh báo về reset sync:** báo như ở cổng 2a.
4. **VCS không có license:** chạy lint và unit TB bằng XSIM, và ghi rõ.

## 8. Độ tin cậy

- **HIGH:**
  - khối đúng như mode 3 đã PASS 27 run;
  - khối rất nhỏ;
  - luật, mẫu TB và cell đều dùng lại cái đã có.
- **MED:**
  - kết quả của E2b-9, vì chưa biết controller AMD phản ứng ra sao;
  - CSV trùng từng byte;
  - ước lượng công.

## 9. Kết quả (2026-10-26)

### 9.1 Bước 2a: khối và kiểm riêng

Lệnh `rtl/run_rtl.sh all`, output ở `work/rtl/`. Cổng 2a đạt.
- **Lint** VCS L1 ở NL = 1, 2, 4: 0 message. **Luật** `check_rtl_rules.py --profile construct`: 0 vi phạm.
- **Unit TB** (VCS):

  | NL | Số lần so với model | Khác | Burst |
  |---|---|---|---|
  | 1 | 926 755 | 0 | 3 008 |
  | 2 | 924 855 | 0 | 6 007 |
  | 4 | 935 860 | 0 | 12 005 |

  - Coverage có đủ mọi trường hợp. Ở NL = 4:
    - sync ở byte đầu 1 578, sync muộn hơn 6 208, không có sync 4 160;
    - nghỉ 1 cycle trước burst 1 183, sync rộng hơn 1 cycle 781;
    - reset giữa burst 18, clock dừng giữa burst 24.
  - Kết quả: `TB RESULT: PASS`. Một bản sửa hỏng của khối làm TB FAIL.
- **Vivado 2025.2 OOC**, xcvp1902, NL = 4, 224 MHz:
  - 6 flip-flop, 6 LUT; WNS +1,089 ns, WHS +0,018 ns;
  - `report_methodology`: 13 cảnh báo, 0 critical warning. AVAL-344 ×1 là thiếu hoạt động RAM cho ước lượng công
    suất; XDCH-2 ×12 là delay min bằng max ở port, do ràng buộc OOC;
  - `report_cdc`: chỉ có đường reset, đã false path, và 2 flop sync có `ASYNC_REG`.

### 9.2 Bước 2b: đưa vào TN2b

Build 1440 Mb/s làm lại (49 s), compile sạch.

**SH_E2b-1** (`+PPI_ADAPTER=1`):
- PASS: 7/7 mục của `check.txt`; `tbcheck` 8/8, có mục `adapter`.
- Khối trùng model ở 10 179 byte clock, 0 khác.
- 6 CSV và `frames.txt` trùng từng byte với bản chạy bằng shim mode 3. `tb.txt` chỉ khác dòng `TB ADAPTER` /
  `TB DIAG`.

**SH_E2b-9** (lỗi SoT sync ở lane 0 của packet 5, tức line 4 của frame 0), 152 s:
- **Không treo:** `TB DONE OK`; `tbcheck` 9/9 (`sotsync`: đúng 1 burst bị đổi); khối trùng model ở 20 802 byte clock.
- **PPI vào R-F:**
  - lane 0 có 52 burst, lane 1–3 có 53;
  - `errsotsynchs` một lần (sample 1330), nằm trong packet 5 của các lane khác, và lúc đó `rxactivehs` của lane 0 = 0.
- **R-X:** 48/48 line; ISR sạch (frame received, stop state).
- **R-F phục hồi:** frame 1 và 2 trùng golden từng pixel, đúng WC và RAW10 ở mọi line.
- **Frame 0 của R-F** (chỉ báo cáo):
  - R-F ra 15 line: 14 line đúng (line 0–3 và 6–15), không có line 4 và 5;
  - thay vào đó là 1 line lẫn: byte của lane 0 là của line 5; byte của lane 1–3 là 17 byte đầu của line 4, rồi phần
    còn lại của line 5, kể từ byte thứ 3 của lane;
  - ISR của R-F: frame received, VC0 frame level (bit 0), CRC (bit 9). Không có bit SoT sync (bit 12), dù PPI có
    `errsotsynchs`;
  - packet count: R-F 47, R-X 48.

**Đọc kết quả E2b-9:**
- Cổng 2b đạt: controller không treo, và frame sau đúng.
- Cái giá của một lỗi sync ở một lane là **hai line của frame đó, trong đó một line sai vẫn được đưa ra `video_out`**.
  ISR có cờ CRC, nhưng `video_out` không đánh dấu line đó, vì `tuser[1]` luôn bằng 0 (`exp2b/README.md` §6.4).
- ⚠️ Cách đọc, chưa kiểm: FIFO của mỗi lane trong controller AMD sâu khoảng 18 phần tử.
  - Khi lane 0 thiếu burst, FIFO của lane 1–3 đầy. Phần còn lại của packet 5 bị mất, cùng vài byte đầu của packet 6.
  - Khi lane 0 bắt đầu packet 6, controller ghép hai packet lại thành line lẫn.
  - Controller căn lại ở packet 7.
- 🔍 Chưa biết D-PHY AMD (R-X) xử lý lỗi sync ra sao. TN2b không có cách cài lỗi sync vào line của TX AMD.
- Quy tắc khác của plan (§7 mục 2: nâng `rxactivehs` cùng `errsotsynchs`) chưa thử. Đây là việc bạn quyết, nếu cần
  so.

### 9.3 Bước 2c: chạy lại TN2b

Cổng 2c đạt.
- **Build:** 4 build làm lại, vì `exp2b.tcl` thêm file của khối; khoảng 49 s mỗi build.
- **Run:** 38 run (29 run `SH_*` còn lại và 9 run `finding`), 3 luồng, 34 phút. Tính cả hai run của 2b: 40 run, tổng
  6 275 s; mỗi run 121–253 s; tối đa 5,1 GB (E2b-8).
- **`evidence`: PASS (12/12 checks).**
  - 277/277 mục của `check.txt` giải mã lại cùng kết luận;
  - `gate`: 31 run `SH_*`, 436 865 byte clock trùng model, 0 khác; SH_E2b-9 như §9.2;
  - hash nguồn `ce12047cbce523a4` ở 40/40 run.
- **`evselftest`: PASS**, 1 ca sạch và 19 lỗi, mỗi lỗi hỏng đúng check của nó. Ba lỗi mới của gate:
  - khối khác model 1 lần: hỏng `gate`, `runs`;
  - 1 pixel của frame 1 R-F trong SH_E2b-9: hỏng `gate`;
  - `rxactivehs` lên trong burst có lỗi sync: hỏng `gate`, `finding`.
- **Hồi quy với `_pre_gate`** (39 run):
  - mọi CSV và `frames.txt` trùng từng byte (282/282 file);
  - `check.txt` trùng 39/39;
  - `tb.txt` chỉ khác dòng `TB ADAPTER` / `TB DIAG`.

  Rủi ro 1 không xảy ra.
- **`run_exp2b.sh recheck`:** 40 run, 31 s; 80 file viết lại trùng từng byte với bản trước.

### 9.4 Bước 2d: docs

- `exp3/TN3_SPEC.md` v0.2: §0 có khối, nối ở đâu và vì sao; §1 sửa định nghĩa R-F; §2 sơ đồ có khối. Không dùng ID
  nội bộ.
- `exp2b/README.md`: tóm tắt, sơ đồ, plusarg, E2b-9, quyết định A, §6.6 (chạy lại và E2b-9), check `gate`,
  evselftest, lệnh.
- `PLAN_TN2B.md`: trỏ sang plan này.
- `fpga/README.md`: cây thư mục, lệnh, trạng thái.
- Memory.
- Quét token ra 0.

### 9.5 Khác với plan

1. **Reset của khối:** dùng 2 flop `ASYNC_REG` riêng trong khối, thay cho cell `m_ftel_dphy_rx_rst_sync` của
   `logical/` (bạn chọn). Lý do: Vivado synth dừng ở cell ASIC (Synth 8-6735).
2. **Port `input var logic`.** Với `` `default_nettype none ``, Vivado synth và XSIM không `--relax` không nhận port
   `input logic` (VRFC 10-1103). Khối là code FPGA mới, nên việc này không đụng RTL của `ftel_dphy_rx`.
3. **Phát hiện kèm theo, mục mở:**
   - RTL của `ftel_dphy_rx` có cùng kiểu port, và chưa từng được synth bằng Vivado; chỉ DC đã synth nó (`syn/`).
   - TN1 và TN2 không thấy, vì XSIM chạy với `--relax` (`exp1/exp1.tcl`), còn VCS, SpyGlass và DC đều nhận kiểu port
     này.
   - Theo quyết định của bạn, RTL không sửa vì tool. Cách xử lý trong flow FPGA để ở TN2c/TN3.
4. **`tbcheck` có thêm mục `sotsync`,** ngoài mục `adapter`: kiểm rằng chỉ đúng burst đã định bị đổi. Ở run có
   `+PPI_SOTSYNCERR`, `regs` và `axis` của R-F chỉ báo cáo; R-X được chấm trong check `gate`.
5. **Kết thúc E2b-9:** TB chờ tới khi 30 µs không RX nào ra line, chứ không chờ riêng R-X đủ line như §4 ghi. Mục
   `axis` vẫn đòi R-X đủ 48 line.
6. **Check `gate`** tính frame có lỗi từ vị trí packet, rồi đòi mọi frame sau đó đúng (ở E2b-9 là frame 1 và 2).
7. **Thời gian:** plan ước 1,35 ngày công cho phần 2; thực tế xong trong ngày 26/10, cùng lúc với phần 1.

### 9.6 Mục mở (chờ bạn)

- Có thử quy tắc khác cho burst lỗi sync (nâng `rxactivehs` cùng `errsotsynchs`) để so với E2b-9 không.
- Cách cho Vivado đọc RTL của `ftel_dphy_rx` ở TN2c/TN3 mà không sửa RTL.
- Commit (đề xuất commit riêng cho phần 1 và phần 2) và push.
