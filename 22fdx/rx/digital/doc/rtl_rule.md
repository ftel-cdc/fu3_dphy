# RTL Coding Rule — `ftel_dphy_rx`

| Mục | Giá trị |
|---|---|
| Ngôn ngữ | SystemVerilog-2012, synthesizable subset |
| Áp dụng cho | Mọi file trong `logical/` (RTL của IP) |
| Phiên bản | 1.2 (2026-10-07), duyệt cùng plan RTL theo HAS v0.13/v0.14: cấu trúc clock của Block No. 1. Lịch sử ở cuối tài liệu |
| Kiểm bằng máy | Luật có nhãn **[M]** được `req_flow/check_rtl_rules.py` kiểm |

Tài liệu này quy định **hình thức** của RTL. **Hành vi** do HAS (`doc/spec.md`) quy định. Khi RTL
cần một hành vi mà HAS chưa định nghĩa thì dừng lại và hỏi (luật T5); không tự chọn hành vi.

---

## 1. Nguồn và thứ tự ưu tiên

| Ưu tiên | Nguồn | Phần dùng |
|---|---|---|
| 1 | IP Wrapper Guideline (FU1, 2026-03-07), Table 1-1 và 1-2 | Tên module, parameter, define, flip-flop, port, instance; port của wrapper; reset active-low ở wrapper |
| 2 | Tiền lệ FX1 | `ip-dev/hw/utils/tool_flow/config/project.yaml` (tiền tố `m_ftel`, layout), header của các cell `m_fpt_lib_*` trong lib fu2, `ftel_intctl` (sync cell tương thích `m_vlsi_synch`, lệnh lint VCS) |
| 3 | [reference rule set] `rtl_rule.md` | R1–R11, P1–P12, cấu trúc module, đã chuyển thể cho IP nhiều clock domain |
| 4 | Tài liệu này | Phần các nguồn trên không quy định |

Khi hai nguồn mâu thuẫn, nguồn có ưu tiên cao hơn thắng.

---

## 2. Đặt tên

### 2.1 Bắt buộc theo Wrapper Guideline

| ID | Đối tượng | Quy tắc | Ví dụ |
|---|---|---|---|
| N1 [M] | Module | `m_ftel_dphy_rx` (core), `m_ftel_dphy_rx_<block>` (khối con), `m_ftel_dphy_rx_wrap` (wrapper). Guideline: `m_<prefix>_<functional name>`, tiền tố FX1 là `m_ftel` | `m_ftel_dphy_rx_cl_ctrl` |
| N2 [M] | Parameter | `PARA_<NAME>`, viết hoa | `PARA_NUM_LANES` |
| N3 [M] | Define | `DEF_<NAME>`, viết hoa | `DEF_DPHY_RX_SIM` |
| N4 [M] | Flip-flop, latch | `reg_<name>`: mọi biến được gán trong `always_ff`, và trong `always_latch` của cell `m_ftel_dphy_rx_cg` (P6) | `reg_state`, `reg_settle_cnt` |
| N5 [M] | Port | `i_<name>`, `o_<name>`. IP này không có `inout` | `i_core_clk`, `o_stopstate` |
| N6 [M] | Instance | `u_<name>_<n>`; số `n` phân biệt các instance cùng loại trong cùng scope | `u_dl_ctrl_0`, `u_sync_2` |
| N7 [M] | Chữ hoa/thường | Tín hiệu và module viết thường; parameter, define, localparam, thành viên enum viết hoa | — |
| N8 | Port của wrapper | `<dir>_dphy_rx_<type>_<name>` (Table 1-2, token `dphy_rx`), xem §2.3 | `i_dphy_rx_cl_enable` |

### 2.2 Phần Guideline không quy định

| ID | Đối tượng | Quy tắc | Lý do |
|---|---|---|---|
| N9 [M] | localparam | `C_<NAME>` | Phân biệt với `PARA_` (override được). Không dùng `LP_` như [reference rule set] vì trong IP này LP là Low-Power |
| N10 [M] | Net tổ hợp | `w_<name>`; next-state của `reg_<name>` là `w_<name>_nxt` | [reference rule set] §2.2; tách được flop và net khi đọc và khi kiểm |
| N11 [M] | Clock / reset của module con | `i_<domain>_clk`, `i_<domain>_rst_n`; `<domain>` ∈ {`core`, `byte`, `cfg`, `ddr`, `ddrn`} (K1). Áp dụng cho input clock và input reset active-low của khối. Core và wrapper dùng tên HAS (§2.3); các cell dùng chung theo K10; reset do khối sinh ra (output) và yêu cầu reset `phy_core_rst` của PPI (tên HAS, chỉ vào reset synchronizer của No.6) không thuộc luật này. Reset nội bộ lấy từ reset synchronizer của chính module có dạng `w_<domain>[_<tên>]_rst_n`. Riêng `m_ftel_dphy_rx_byte_clk` được dùng clock `w_ddrn_clk` do chính nó sinh qua cell clock inverter (K2) | Theo mẫu `i_i2c_clk`, `i_i2c_rst_n` của Table 1-2 |
| N12 [M] | Package, kiểu | Package `ftel_dphy_rx[_<name>]_pkg` (package không phải module nên không có `m_`); kiểu có hậu tố `_t` | `ftel_dphy_rx_pkg::dl_state_t` |
| N13 [M] | Nhãn | `g_<name>` cho generate, `p_<name>` cho always, `a_<name>` cho assertion | `g_lane`, `p_state_reg` |
| N14 | Tên theo HAS | Tín hiệu nội bộ dùng lại tên của HAS khi HAS có tên, bỏ hậu tố `_x` của lane | `reg_stopstate`, `w_sync_search_start` |
| N15 | Viết tắt | Chỉ các viết tắt HAS đã dùng: `hs lp esc ulps sot eot cl dl cfg sts afe ppi cnt en rst clk nxt dly tap sync ddr div deser act` | — |

### 2.3 Port của wrapper `m_ftel_dphy_rx_wrap`

| Loại (Table 1-2) | Mẫu | Port |
|---|---|---|
| CLOCK | `i_dphy_rx_<name>` | `i_dphy_rx_core_clk` |
| RESET | `i_dphy_rx_<name>_n`, active-low | `i_dphy_rx_phy_core_rst_n`. Core nhận `phy_core_rst` active-high (HAS §4.2, OPEN K6), nên inverter nằm trong wrapper |
| Others: PPI | `<dir>_dphy_rx_<tên PPI>` | `i_dphy_rx_cl_enable`, `i_dphy_rx_dl_enable`, `o_dphy_rx_rxbyteclkhs`, `o_dphy_rx_rxdatahs`, … |
| Others: AFE | `<dir>_dphy_rx_afe_<tên>` | `i_dphy_rx_afe_lp_dp`, `i_dphy_rx_afe_cl_hs_clk`, `i_dphy_rx_afe_hs_bit`, `o_dphy_rx_afe_hs_en`, … |
| Others: cấu hình (placeholder, OPEN K3) | `i_dphy_rx_cfg_<field>` | `i_dphy_rx_cfg_hs_settle_cyc`, … |
| Others: trạng thái (placeholder, OPEN K3) | `o_dphy_rx_sts_<name>` | `o_dphy_rx_sts_dl_state`, … |
| BUS, INT, PAD, CSR | — | Không có trong bản này: không bus (K3), không interrupt, không pad |

- Tín hiệu có một bản cho mỗi lane (hậu tố `_x` trong HAS) là packed array theo lane: `[PARA_NUM_LANES-1:0]`,
  và `[PARA_NUM_LANES-1:0][PARA_DESER_RATIO-1:0]` cho dữ liệu. Port PPI đánh chỉ số theo lane logic,
  port AFE theo lane vật lý.
- Wrapper không chứa logic, ngoài inverter của reset và việc đổi tên/nối port.

---

## 3. File và module

| ID | Quy tắc |
|---|---|
| F1 [M] | Một module hoặc package mỗi file. Tên file = tên module + `.sv`. Mọi file nằm phẳng trong `logical/` |
| F2 [M] | Thứ tự trong file: header (§3.1), rồi `` `timescale 1ns/1ps ``, rồi `` `default_nettype none ``, rồi `module`…`endmodule` (hoặc `package`…`endpackage`). Dòng cuối là `` `default_nettype wire `` |
| F3 [M] | Header theo mẫu §3.1, có đủ các trường `Module`, `Description`, `HAS`, `Clock domains`, `REQ-IDs`, `OPEN` |
| F4 | Thứ tự trong module: `import` → `#(...)` parameter → port → localparam → khai báo `reg_` rồi `w_` → `always_comb`/`assign` → `always_ff` → instance → assertion (bọc `` `ifndef SYNTHESIS ``) |
| F5 | Thứ tự port: clock → reset → điều khiển → dữ liệu vào → dữ liệu ra → trạng thái → AFE → cấu hình. Mỗi nhóm mở bằng `// ---- <nhóm> ----` |
| F6 [M] | Instance chỉ dùng kết nối theo tên `.port(sig)` và override parameter theo tên. Cấm `.*` và kết nối theo vị trí |
| F7 | Comment tiếng Anh; nói **vì sao**, không lặp lại code; không để code chết (git giữ lịch sử) |
| F8 | File sinh tự động (`ftel_dphy_rx_config_pkg.sv`) ghi `Generated by validate_config.py — DO NOT EDIT` trong header và không sửa tay |

### 3.1 Mẫu header

Theo header của các cell `m_fpt_lib_*` (FX1 lib), thêm các trường truy vết:

```systemverilog
//------------------------------------------------------------------------------
// Copyright (c) 2026 FPT Telecom. All rights reserved.
//
// This RTL source code and the associated design are the proprietary
// and confidential information of FPT Telecom.
// Any unauthorized use, reproduction, or disclosure is strictly prohibited.
//------------------------------------------------------------------------------
// Author          : Ho Khanh Linh
// Email           : linhhk26@fpt.com
// Created Date    : 2026-10-03
// Module          : m_ftel_dphy_rx_cl_ctrl
// Description     : Clock lane control, CIL-SCNN (HAS Block No. 2).
// Parent          : m_ftel_dphy_rx
// HAS             : draft v0.14, §4.4, Table 4-4, Figure 4-4
// Clock domains   : core
// REQ-IDs         : REQ-086, REQ-087, ...
// OPEN            : none
//
// Evolution History:
// -----------------------------------------------------------------------------
// Date         Version    Author        Description
// 2026-10-03   0.1        Ho Khanh Linh Draft against HAS v0.11; open items at their defaults.
//
// This section is not intended for routine updates or minor design changes.
// A new version is strictly reserved for major architectural shifts
// that require software modifications across different chip generations.
//------------------------------------------------------------------------------
```

---

## 4. Coding

### 4.1 Bắt buộc

| ID | Quy tắc |
|---|---|
| R1 [M] | Logic tuần tự chỉ dùng `always_ff @(posedge i_<d>_clk or negedge i_<d>_rst_n)`; flip-flop dữ liệu không reset (K4) dùng `always_ff @(posedge i_<d>_clk)`. Block No. 6, nơi sinh reset, dùng reset `w_<d>_rst_n` lấy từ `m_ftel_dphy_rx_rst_sync` của chính nó |
| R2 [M] | Logic tổ hợp chỉ dùng `always_comb` hoặc `assign` |
| R3 | Trong `always_ff` chỉ dùng `<=`; trong `always_comb` chỉ dùng `=` |
| R4 | Mỗi `always_comb` gán giá trị mặc định cho mọi biến nó lái ngay ở đầu khối, để không sinh latch |
| R5 | Mỗi tín hiệu chỉ có một nơi lái |
| R6 | Mỗi `case` có `default`. Chỉ dùng `unique`/`priority` khi danh sách đủ và loại trừ nhau |
| R7 [M] | Kiểu dữ liệu là `logic`; `int`/`int unsigned` chỉ cho parameter và hằng; `genvar` cho generate. Cấm `reg`, `wire`, `integer` |
| R8 [M] | Mỗi khối `always_ff`/`always_comb` có nhãn `p_<name>` |
| R9 | Độ rộng khớp tường minh; dùng cast `W'(x)` thay vì để tool tự cắt hoặc mở rộng |
| R10 | Module có flip-flop nhận đủ clock và reset của domain; module thuần tổ hợp không có port clock |
| R11 | Không có số "thần kỳ": hằng phải là `PARA_`, `C_` hoặc hằng của package. Ví dụ: mã escape của Table 4-6, leader `00011101`. Được dùng trực tiếp: `0`, `1`, `'0`, `'1` |
| R12 | Mỗi FSM: kiểu enum trong `ftel_dphy_rx_pkg`, thanh ghi `reg_state`, next-state `w_state_nxt` tính trong `always_comb`. Output đi ra AFE hoặc PPI là thanh ghi khi HAS yêu cầu không glitch (HAS §4.4, §4.5) |

### 4.2 Cấm

| ID | Cấm | Lý do |
|---|---|---|
| P1 [M] | `#delay` | Không tổng hợp được |
| P2 [M] | `initial` | Chỉ dùng trong TB. Kiểm tra tĩnh lúc elaborate đặt trong `` `ifndef SYNTHESIS `` |
| P3 [M] | `casex`, `casez` | Lệch giữa mô phỏng và tổng hợp |
| P4 [M] | `defparam` | Override theo tên ở instance |
| P5 [M] | Net ngầm định | `` `default_nettype none `` (F2) |
| P6 [M] | `always @`, `always_latch` | Dùng `always_ff`/`always_comb` (R1, R2). Ngoại lệ duy nhất: `always_latch` trong cell `m_ftel_dphy_rx_cg`, latch của ICG (K2, K10) |
| P7 | Latch | Ngoại lệ duy nhất: latch của ICG trong `m_ftel_dphy_rx_cg` (P6) |
| P8 | Một net nhiều nơi lái | — |
| P9 | Function có side effect hoặc biến `static` | — |
| P10 [M] | `$display`, `$random` và system task khác ngoài `` `ifndef SYNTHESIS `` | Chỉ cho TB và kiểm tra tĩnh |
| P11 [M] | `inout` | IP không có pad hay tín hiệu analog |
| P12 [M] | `negedge` của clock | Chỉ được dùng cho reset (R1) |

---

## 5. Clock, reset và CDC

| ID | Quy tắc |
|---|---|
| K1 | Năm domain: `core` (`core_clk`, 200 MHz), `byte` (`rxbyteclkhs`, line rate / 8), `cfg` (clock cấu hình, chưa có cho tới khi đóng K3), `ddr` (DDR clock `afe_cl_hs_clk`, line rate / 2, chỉ trong Block No. 1) và `ddrn` (DDR clock đảo, ra từ cell clock inverter; các flop cạnh xuống của Block No. 1, HAS §4.3). Mỗi flip-flop thuộc đúng một domain; header ghi các domain của module |
| K2 | Không clock theo cạnh xuống, không gate clock, không logic trên đường clock. Ngoại lệ duy nhất là cấu trúc clock của Block No. 1 (HAS §4.3). Nó chỉ được nằm trong `m_ftel_dphy_rx_byte_clk`, và mỗi chỗ mang tag `// CLK_STRUCT (HAS §4.3)`: (1) DDR clock đảo `ddrn`, sinh bằng cell `m_ftel_dphy_rx_clk_inv`: cạnh xuống của DDR clock thành cạnh lên của `ddrn`, nên vẫn không dùng `negedge` (P12); (2) flop của bộ chia 4 dùng làm clock; (3) ICG `m_ftel_dphy_rx_cg` sinh `rxbyteclkhs`; (4) output của reset synchronizer byte-clock enable làm enable của ICG (đồng thời là reset của bộ chia và pha load, K3). `rxclkesc_x` là XOR của LP line đã sync, chỉ xuất ra PPI; bên trong IP không có gì chạy bằng nó (HAS §4.9, ADR-002) |
| K3 | Reset nội bộ active-low: assert bất đồng bộ, release đồng bộ. Mỗi domain có một `m_ftel_dphy_rx_rst_sync` trong No.6; Block No. 4 của mỗi lane có thêm một bộ trong domain `byte`, bị clear khi lane bị tắt (HAS §4.2). Bộ chia và pha load của Block No. 1 dùng reset synchronizer của byte-clock enable trong `m_ftel_dphy_rx_byte_clk`, nên bị giữ reset khi gate đóng (HAS §4.1, §4.3). Flop của domain `ddrn` dùng reset của domain `ddr`: reset release ở cạnh lên, flop `ddrn` nhận ở cạnh xuống sau đó nửa chu kỳ (K11) |
| K4 | Flip-flop điều khiển (FSM, cờ valid/active, counter, enable, output) bắt buộc có reset. Flip-flop dữ liệu (word, byte, byte trong delay line; sampler, shift register và parallel register của deserializer) được bỏ reset vì luôn đi kèm cờ valid đã reset |
| K5 [M] | Mọi crossing đi qua một trong ba cell: level sync `m_ftel_dphy_rx_sync`, toggle sync `m_ftel_dphy_rx_tsync`, reset sync `m_ftel_dphy_rx_rst_sync`. Mỗi instance có tag `// CDC_CROSSING: <src> -> <dst>: <signal> (HAS §4.1, Table 4-2)` |
| K6 [M] | Trường cấu hình quasi-static đi thẳng không qua sync và mang tag `// CDC_QUASI_STATIC: <field> (HAS §4.1)`. Phần mềm chỉ đổi chúng khi các lane liên quan đang tắt |
| K7 [M] | Output PPI của domain `byte` được gate tổ hợp bằng enable đã sync trong `core`, chỉ trong No.7, kèm tag `// CDC_GATING (HAS §4.9)` |
| K8 | Input bất đồng bộ từ AFE (LP-RX) chỉ vào qua level sync `PARA_LP_SYNC_STAGES` tầng. `afe_hs_bit_x` là input source-synchronous: sampler của Block No. 1 lấy mẫu thẳng bằng DDR clock, không qua sync (HAS §4.1, Table 4-2) |
| K9 | Không có đường tổ hợp từ domain này vào flip-flop của domain khác, ngoài các trường hợp K5–K7 |
| K10 [M] | Ngoại lệ của N11 cho năm cell dùng chung, vì chúng nằm ở nhiều domain hoặc giữ port của cell lib fu2: `m_ftel_dphy_rx_sync` giữ port của `m_vlsi_synch` (`PARA_LEVELS`, `i_clk`, `i_rstn`, `i_data_in`, `o_data_out`) và `m_ftel_dphy_rx_rst_sync` giữ port của `m_fpt_lib_reset_sync_rising_edge_async_reset_n` (`i_clk`, `i_async_reset_n`, `o_sync_reset_n`), để lúc tích hợp chỉ cần thay tên module (như `ftel_intctl_sync`); `m_ftel_dphy_rx_tsync` nối hai domain nên đặt tên theo vai trò: `i_src_clk`, `i_src_rst_n`, `i_dst_clk`, `i_dst_rst_n`. Hai cell clock giữ port của cell lib fu2: `m_ftel_dphy_rx_cg` theo `m_fpt_lib_cg` (`i_clk`, `i_en`, `i_scan_en`, `o_clk`) và `m_ftel_dphy_rx_clk_inv` theo `m_fpt_lib_clk_inv` (`i_in`, `o_out`) |
| K11 | `ddr`, `ddrn` và `byte` là một họ clock đồng bộ, cùng sinh từ DDR clock. Đường giữa chúng đi thẳng flop → flop, không qua cell sync, và do STA kiểm (HAS §4.3): `ddr` → `ddrn` nửa chu kỳ (chỉ đường pha load), `ddr`/`ddrn` → `byte` nhiều chu kỳ DDR. Flop nhận mang tag `// SYNC_DDR (HAS §4.3)` |
| K12 [M] | Instance của hai cell clock `m_ftel_dphy_rx_cg` và `m_ftel_dphy_rx_clk_inv` chỉ được đặt trong `m_ftel_dphy_rx_byte_clk`. Tên instance theo quy ước của lib fu2 `u_dont_touch_<name>_<n>`, để flow tổng hợp không tối ưu chúng. Mỗi instance mang tag `// CLK_STRUCT (HAS §4.3)` (K2) |

---

## 6. Truy vết

| ID | Quy tắc |
|---|---|
| T1 [M] | Header liệt kê `REQ-IDs` của mọi REQ mà file cài đặt, và mục HAS (`HAS: draft v0.11, §…`) |
| T2 [M] | Mỗi khối `always`, nhóm `assign` hoặc instance cài đặt một REQ có comment `// REQ-xxx[, REQ-yyy]` ngay trên hoặc cùng dòng |
| T3 [M] | REQ cần người quyết (provisional) được cài ở đúng một chỗ: một hằng, một parameter hoặc một khối. Chỗ đó mang tag `// OPEN <id> REQ-xxx: <default đang dùng>`, với `<id>` có trong Table 9-1 của HAS |
| T4 | Quyết định vi kiến trúc mà HAS không cố định mang tag `// D-n`, giải thích ở `doc/rtl_notes.md` |
| T5 | Hành vi HAS không định nghĩa: ghi câu hỏi Q-n trong `doc/rtl_notes.md` và dừng (CF-GAP); chưa viết phần đó cho tới khi có câu trả lời |
| T6 [M] | REQ-ID trong tag phải có trong `req/structured_spec.json`. ID ổn định qua các revision của spec (`req_flow/README.md`) |

---

## 7. Lint và kiểm

| ID | Kiểm | Tiêu chí |
|---|---|---|
| L1 | VCS `vcs -full64 -sverilog +lint=all,noVCDE`: từng module kèm các module nó dùng; wrapper với `PARA_NUM_LANES` = 1, 2, 4 | 0 Error, 0 Warning, 0 Lint |
| L2 | SpyGlass `lint/lint_rtl` qua tool_flow (`run_ip_tool.py --ip dphy_rx --tool lint`) | 0 Fatal, 0 Error; Warning chỉ được waive trong `lint/lint_waiver.tcl`, mỗi dòng ghi REQ/ADR/D-n |
| L3 | `check_rtl_rules.py logical/` | 0 vi phạm các luật [M] |
| L4 | `flow_check.py --phase P3a` | 0 xung đột (CF-LINT, CF-COVER, CF-TAG, CF-DRIFT, CF-SPEC) |

**Checklist trước khi commit:** L1–L4 đạt; không còn Q-n chưa trả lời trong phần đã viết; mọi D-n có
giải thích trong `rtl_notes.md`; header đủ trường.

---

## 8. Ví dụ đúng / sai

| Sai | Đúng | Luật |
|---|---|---|
| `module dl_ctrl` | `module m_ftel_dphy_rx_dl_ctrl` | N1 |
| `parameter LANES = 4` | `parameter int PARA_NUM_LANES = 4` | N2 |
| `localparam LP_ULPS = 8'b00011110` | `localparam logic [7:0] C_ESC_ULPS = 8'b00011110` | N9, R11 |
| `logic [3:0] state;` gán trong `always_ff` | `dl_state_t reg_state;` | N4, R12 |
| `always @(posedge clk)` | `always_ff @(posedge i_core_clk or negedge i_core_rst_n) begin : p_state_reg` | R1, R8, N11 |
| `u_sync (clk, rstn, d, q)` | `u_sync_0 (.i_clk(i_core_clk), .i_rstn(i_core_rst_n), .i_data_in(w_d), .o_data_out(w_q))` | F6, N6, K10 |
| Flop `core` lấy thẳng tín hiệu `byte` | Qua `m_ftel_dphy_rx_tsync` / `m_ftel_dphy_rx_sync`, kèm tag `CDC_CROSSING` | K5 |
| `if (cnt == 19)` | `if (reg_settle_cnt == i_cfg.hs_settle_cyc)` | R11 |

---

## Lịch sử

| Phiên bản | Ngày | Thay đổi |
|---|---|---|
| 0.1 | 2026-10-03 | Bản nháp đầu, theo plan RTL nháp (M0) |
| 1.0 | 2026-10-03 | Đã duyệt; Author và Email của header. Bổ sung khi viết `check_rtl_rules.py`, ba chỗ bản 0.1 chưa phủ: K10 thêm cell reset sync (port của cell lib fu2) và cell toggle sync (tên theo vai trò src/dst); R1 ghi rõ dạng của flip-flop dữ liệu không reset (K4); F2 áp dụng cả cho package |
| 1.1 | 2026-10-03 | Làm rõ khi viết RTL (M2): N11 áp dụng cho input clock và input reset active-low, không cho reset sinh ra hay `phy_core_rst` của PPI; R1 cho phép Block No. 6 dùng reset do chính nó đồng bộ. Checker sửa theo |
| 1.2 | 2026-10-07 | Duyệt cùng plan RTL theo HAS v0.13/v0.14 (ADR-001 phương án A): Block No. 1 có sampler, deserializer, byte clock và clock activity. K1 và N11 thêm domain `ddr`, `ddrn`; K2 cho phép đúng bốn cấu trúc clock trong `m_ftel_dphy_rx_byte_clk`, tag `CLK_STRUCT`; K3 thêm reset của bộ chia và pha load; K4 thêm flop dữ liệu của deserializer; K8 bỏ `afe_cl_clk_active`, thêm `afe_hs_bit_x`; K10 thêm hai cell clock; K11 mới (họ clock đồng bộ, tag `SYNC_DDR`); K12 [M] mới (cell clock chỉ trong `byte_clk`); N4, P6, P7 cho phép latch của ICG; N15 thêm `ddr div deser act`; §2.3 ví dụ port AFE. Checker sửa theo |
