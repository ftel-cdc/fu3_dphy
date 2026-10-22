# TN1 — Mô tả thí nghiệm: so RX D-PHY `ftel_dphy_rx` với RX D-PHY của AMD trong mô phỏng XSIM

> Tài liệu cho team FPGA: lấy RTL và testbench ở đâu, bench gồm những gì, so theo luật nào, chạy và đọc kết quả ra
> sao. Kết quả lần chạy ngày 2026-10-20 nằm ở [`TN1_REPORT.md`](TN1_REPORT.md).
> Phiên bản 1.0, ngày 2026-10-22. Nhóm D-PHY RX viết.

## 1. Thí nghiệm làm gì

Testbench tạo một tín hiệu D-PHY (clock lane và 1, 2 hoặc 4 data lane) và đưa cùng lúc vào hai bộ thu:
- **RX của AMD:** IP `mipi_dphy` 4.3 của Vivado, chế độ SLAVE. IP này đã được dùng thực tế, nên nó là mốc: nếu
  RX AMD nhận đúng thì tín hiệu phát ra đúng chuẩn, và lỗi nào chỉ xuất hiện ở RX kia là lỗi của RX kia.
- **RX của mình:** RTL ASIC `ftel_dphy_rx`, lấy nguyên từ repo, không sửa gì cho mô phỏng.

Đầu ra PPI của mỗi RX được ghi thành một file CSV đúng định dạng ILA của Vivado, rồi được so với danh sách byte đã
phát (file truth).

Thí nghiệm trả lời ba câu hỏi:
1. Cùng một tín hiệu trên pad, hai RX có cho ra cùng dữ liệu ở PPI không?
2. Mỗi RX có nhận đúng các byte đã phát không?
3. Khi hai RX đứng sau cùng một front end và chạy cùng bộ kịch bản, phần digital của RX mình có làm được như phần
   digital của RX AMD không?

TN1 có thể không cần board. Mọi thứ chạy trong XSIM của Vivado.

## 2. Lấy RTL và testbench ở đâu

Repo `https://github.com/ftel-cdc/fu3_dphy`, nhánh `dev`. RTL và bench đã cho ra kết quả ngày 2026-10-20 có trên
nhánh này từ commit `66f9f39`. Khi chuyển sang repo này, các file chỉ được thêm header và đổi đường dẫn. Lần chạy lại
E1-1 trong repo mới cho capture giống từng byte với lần chạy cũ.

```bash
git clone -b dev https://github.com/ftel-cdc/fu3_dphy.git
cd fu3_dphy/22fdx/rx/digital          # mọi lệnh trong tài liệu này chạy từ đây
```

Đường dẫn trong bảng tính từ `22fdx/rx/digital`.

| Thành phần | Đường dẫn | Ghi chú |
|---|---|---|
| RTL `ftel_dphy_rx` | [`logical/`](../../logical/) | 22 file SystemVerilog. Thứ tự compile ở [`logical/filelist.f`](../../logical/filelist.f); đường dẫn trong đó bắt đầu bằng `${FTEL_DPHY_RX_PATH}`, script tự thay. Top là [`m_ftel_dphy_rx_wrap.sv`](../../logical/m_ftel_dphy_rx_wrap.sv) |
| Package cấu hình | [`logical/ftel_dphy_rx_config_pkg.sv`](../../logical/ftel_dphy_rx_config_pkg.sv) | Sinh từ [`config/ftel_dphy_rx.yaml`](../../config/ftel_dphy_rx.yaml) bằng [`config/validate_config.py`](../../config/validate_config.py); đã có sẵn, không cần sinh lại |
| Testbench top | [`fpga/exp1/tb_exp1.sv`](tb_exp1.sv) | Danh sách plusarg nằm ở đầu file |
| Line generator | [`fpga/exp1/dphy_line_gen.sv`](dphy_line_gen.sv) | TX giả: phát tín hiệu D-PHY và ghi file truth |
| Mô hình AFE | [`fpga/exp1/afe_model.sv`](afe_model.sv) | AFE lý tưởng, đồng thời kiểm trạng thái line và tín hiệu bật terminal |
| Monitor PPI | [`fpga/exp1/ppi_csv_mon.sv`](ppi_csv_mon.sv) | Ghi PPI ra CSV định dạng ILA |
| Khối thay RX AMD | [`fpga/exp1/xrx_stub.sv`](xrx_stub.sv) | Khối rỗng, dùng khi chỉ chạy RX mình (chế độ `stub`) |
| Script Vivado | [`fpga/exp1/exp1.tcl`](exp1.tcl) | Tạo IP `mipi_dphy` (tên module `xrx`) theo rate và số lane, tạo project, compile, elaborate |
| Script chạy | [`fpga/exp1/run_exp1.sh`](run_exp1.sh) | Build, chạy kịch bản, kiểm kết quả; cách dùng in ở đầu file |
| Cấu hình theo rate | [`fpga/exp1/cfg_for_rate.py`](cfg_for_rate.py) | Field run-time của RX mình theo rate, lấy từ model trong `config/validate_config.py` |
| Bộ so | [`fpga/tools/csi2_dump.py`](../tools/csi2_dump.py) | Mode `bursts` so CSV với truth. Cùng công cụ này đọc được capture ILA thật |
| Kiểm chứng | [`fpga/exp1/tn1_evidence.py`](tn1_evidence.py), [`fpga/exp1/neg_front.sh`](neg_front.sh), [`fpga/exp1/eot_window.py`](eot_window.py) | Kiểm lại toàn bộ output bằng code riêng; phép thử âm; bảng đo cửa sổ cắt trailer |
| Đặc tả RX mình | [`doc/spec.md`](../../doc/spec.md) | HAS, đặc tả kiến trúc của `ftel_dphy_rx`: PPI, giao tiếp với AFE, field cấu hình, bảng giới hạn trailer |
| Ghi chép kỹ thuật | [`fpga/exp1/README.md`](README.md) | Ghi chép nội bộ của nhóm D-PHY RX về TN1, chi tiết hơn tài liệu này |
| Testbench riêng của khối lấy mẫu | [`sim/tb_afe_adapter/`](../../sim/tb_afe_adapter/) | Testbench VCS cho khối lấy mẫu và giải nối tiếp, không thuộc TN1 |

## 3. Môi trường

- **Vivado 2025.2**, dùng XSIM đi kèm. Script mặc định gọi `/opt/xilinx/2025.2/Vivado/bin/vivado`. Nếu Vivado nằm
  chỗ khác thì đặt biến `VIVADO`, ví dụ `VIVADO=/tools/Vivado/2025.2/bin/vivado fpga/exp1/run_exp1.sh E1-1`.
- **Part** `xcvp1902-vsva6865-2MP-e-S`, không cần board. IP `mipi_dphy` 4.3 được script tự tạo và không cần license.
- **Python 3** có PyYAML, vì bộ kiểm cấu hình đọc file YAML. Các script khác chỉ dùng thư viện chuẩn.
- **Linux, bash.**
- **Thời gian:**
  - mỗi tổ hợp rate × số lane cần một build: khoảng 5 phút lần đầu, vài giây nếu chỉ testbench đổi;
  - một kịch bản chạy khoảng 10–15 s với cả hai RX, vài giây ở chế độ `stub`;
  - `all` khoảng 23 phút, `model` khoảng 23 phút, `window` khoảng 7 phút, nếu chạy tuần tự.
- **Chạy song song:** các lệnh dùng build khác nhau chạy song song được. Hai lệnh không được dùng chung một build cùng
  lúc.
- **Đĩa:** output nằm ở `fpga/work/exp1/` (git bỏ qua), khoảng 1–2 GB cho một bộ đầy đủ.

## 4. Sơ đồ

```
dphy_line_gen (TX giả, D-PHY v1.1, mức logic trên pad) ──► truth.txt (byte đã phát, theo lane và burst)
   │ clk_p/n, d_p/n[0..3]
   ├─► RX AMD: mipi_dphy 4.3 SLAVE (IBUFDS_DPHY → XPHY → controller) ──────────► PPI ─► xil_ppi.csv ──┐
   ├─► IBUFDS_DPHY (cùng model, cùng SIM_DEVICE), mặc định: +AFE=xil ──┐                                  │
   │                                                                   ├─► ftel_dphy_rx ─► PPI ─► ftel_ppi.csv ─┤
   └─► afe_model (AFE lý tưởng), khi đặt +AFE=model ──────────────────┘                                  │
                                       csi2_dump.py bursts: mỗi CSV được so với truth.txt ◄──────────────┘

Kiểm trong bench: đầu ra LP của buffer bên RX AMD và của buffer trước RX mình phải trùng nhau ở mọi lần đổi.
```

## 5. Các khối của bench

### 5.1 Line generator ([`dphy_line_gen.sv`](dphy_line_gen.sv))

- **Clock lane:** đi LP-11 → LP-01 → LP-00 → HS-0 một lần, rồi chạy continuous. Cạnh clock nằm giữa bit.
- **Mỗi burst, mọi lane phát cùng lúc:** LP-11 → LP-01 (TLPX) → LP-00 (THS-PREPARE) → HS-0 (THS-ZERO) → sync 0xB8 →
  payload (LSB trước) → trail (đảo của bit cuối, dài THS-TRAIL) → LP-11. Sau đó chờ THS-EXIT rồi mới phát burst kế.
- **Mức trên pad:** chỉ là mức logic, không có analog. Khi HS thì Dp = bit, Dn = ~bit. Skew của từng lane là
  transport delay.
- **Timing mặc định** nằm giữa khoảng cho phép của D-PHY v1.1. Ví dụ ở 1440 Mb/s:
  - TLPX 75 ns, THS-PREPARE 66 ns;
  - PREPARE + ZERO bằng 1,2 lần mức min (182 ns so với 152 ns);
  - THS-TRAIL bằng 1,2 lần mức min (75 ns), THS-EXIT 150 ns.
- **Payload:** mẫu `counter` theo lane (mặc định), `prbs9`, hoặc `synclike` (chứa 0xB8 và 0xB8 dịch 1–7 bit qua
  ranh giới byte). Độ dài mặc định mỗi burst là 1, 2, 3, 4, 5, 8, 16, 64, 256 rồi 1024 byte mỗi lane.
- **File truth:** ghi cho từng lane và từng burst: số byte, thời điểm bit sync đầu tiên, thời điểm kết thúc payload,
  và payload.

### 5.2 Front end trước RX mình

RX mình nhận tín hiệu từ một front end (vai trò của AFE trên chip). Có hai lựa chọn:

- **`IBUFDS_DPHY` (mặc định, `+AFE=xil`).**
  - Đây là primitive mà IP AMD đặt ở mỗi cặp pin. Bench dùng cùng `SIM_DEVICE "VERSAL_PREMIUM"`, một buffer cho mỗi
    data lane và một cho clock lane.
  - LP receiver luôn bật, như trong IP AMD. HS receiver bật theo tín hiệu `hs_en` của RX mình; bên AMD thì controller
    của AMD tự bật.
  - Pad vào cả hai bộ buffer đều là strong, vì IP AMD đưa pad tới buffer bằng một `assign` thường. Hệ quả cho cả hai
    RX: trong HS, đầu ra LP của model đổi theo data (trên silicon thì đọc LP-00), và sau LP-11, đầu ra HS giữ bit cuối.
- **`afe_model` (`+AFE=model`).**
  - Suy ra trạng thái line từ chuỗi LP trên pad. Trong HS, đầu ra LP đọc LP-00, giống silicon.
  - Đầu ra HS bằng Dp khi đang HS và `hs_en` bật, ngoài ra bằng 0. Mô hình không có trễ.
  - Ở cả hai chế độ, `afe_model` luôn chạy song song để kiểm: tín hiệu bật terminal có bật kịp trong khoảng
    TD-TERM-EN không, và trạng thái line suy ra có khớp với generator không.

### 5.3 RX AMD ([`exp1.tcl`](exp1.tcl))

- IP `mipi_dphy` 4.3, SLAVE, SupportLevel 1, `C_INIT` 99 µs. Các tham số khác để mặc định của IP theo rate.
- Line rate cố định lúc build, nên mỗi tổ hợp rate × số lane là một build riêng.
- Trên xcvp1902, IP này chỉ build được ở 260–3200 Mb/s. Rate thấp hơn thì chạy RX mình một mình (chế độ `stub`).

### 5.4 RX mình

Module `m_ftel_dphy_rx_wrap`, tham số `PARA_NUM_LANES` bằng số lane của build. Cách testbench nối:

| Cổng | Nối với | Ý nghĩa |
|---|---|---|
| `i_dphy_rx_core_clk` | Clock 200 MHz của testbench | Clock chính, cùng clock với RX AMD |
| `i_dphy_rx_phy_core_rst_n` | Reset của testbench | Reset, tích cực mức thấp |
| `i_dphy_rx_afe_lp_dp/dn[NL-1:0]`, `i_dphy_rx_afe_cl_lp_dp/dn` | Đầu ra LP của front end | Mức LP của từng data lane và của clock lane |
| `i_dphy_rx_afe_hs_bit[NL-1:0]` | Đầu ra HS của front end, data lane | Bit HS nối tiếp |
| `i_dphy_rx_afe_cl_hs_clk` | Đầu ra HS của front end, clock lane | Clock HS DDR, tần số bằng nửa line rate |
| `o_dphy_rx_afe_hs_en[NL-1:0]`, `o_dphy_rx_afe_cl_hs_en` | `HSRX_DISABLE` của buffer, qua cổng đảo | RX mình tự bật bộ thu HS |
| `o_dphy_rx_afe_term_en`, `o_dphy_rx_afe_cl_term_en` | `afe_model`, chỉ để kiểm | Bật điện trở terminal |
| `i_dphy_rx_cl_enable`, `i_dphy_rx_dl_enable`, `i_dphy_rx_forcerxmode` | Hằng: 1, 1, 0 | Bật mọi lane |
| `i_dphy_rx_cfg_*` | Giá trị theo rate (bảng dưới) | Field cấu hình run-time |
| `o_dphy_rx_rxbyteclkhs`, `_rxdatahs`, `_rxvalidhs`, `_rxactivehs`, `_rxsynchs`, `_errsoths`, `_errsotsynchs`, `_stopstate`, `_cl_stopstate`, `_init_done` | Monitor | PPI theo D-PHY |

**Cấu hình theo rate.** [`cfg_for_rate.py`](cfg_for_rate.py) lấy giá trị từ model trong
[`config/validate_config.py`](../../config/validate_config.py). Không giá trị nào được chỉnh
tay. `tinit_cyc` là 20000 (100 µs ở 200 MHz). Các field khác lấy giá trị reset của package cấu hình.

| Rate (Mb/s) | `hs_settle_cyc` | `clk_settle_cyc` | `eot_skip_bytes` |
|---|---|---|---|
| 80 | 70 | 33 | 0 |
| 260 | 33 | 33 | 1 |
| 400 | 27 | 33 | 2 |
| 600 | 23 | 33 | 4 |
| 800 | 21 | 33 | 6 |
| 1000 | 20 | 33 | 9 |
| 1200 | 20 | 33 | 11 |
| 1440 | 19 | 33 | 13 |
| 1500 | 19 | 33 | 14 |

`eot_skip_bytes` là số byte RX mình bỏ ở cuối mỗi burst. RX mình giữ 32 byte cuối trong một delay line; khi thấy line
về LP-11, nó bỏ đi phần trail ở cuối. RX AMD không cắt trailer.

### 5.5 Monitor ([`ppi_csv_mon.sv`](ppi_csv_mon.sv))

- Mỗi RX ghi một file CSV đúng định dạng ILA của Vivado: `xil_ppi.csv` cho RX AMD, `ftel_ppi.csv` cho RX mình.
- Mẫu được lấy ở cạnh lên `rxbyteclkhs` của chính RX đó.
- Cột theo lane n: `dl{n}_rxdatahs`, `dl{n}_rxvalidhs`, `dl{n}_rxactivehs`, `dl{n}_rxsynchs`, `dl{n}_errsoths`,
  `dl{n}_errsotsynchs`, `dl{n}_stopstate`, và `cl_stopstate`.

### 5.6 Trình tự một lần chạy

1. Nhả reset.
2. Chờ cả hai RX báo `init_done`, khoảng 100 µs, line đứng ở LP-11.
3. Clock lane vào HS.
4. Phát lần lượt các burst.
5. Chờ delay line của RX mình xả hết rồi kết thúc.

## 6. Luật so và tiêu chí đạt

Hai RX không được so trực tiếp từng chu kỳ với nhau, vì mỗi RX có byte clock và độ trễ riêng. Thay vào đó, mỗi CSV
được so với cùng một file truth theo cùng một bộ luật ([`csi2_dump.py`](../tools/csi2_dump.py), mode `bursts`).

**Một burst trên một lane đạt khi đủ mọi điều kiện sau:**

| Điều kiện | Cách kiểm |
|---|---|
| Burst | Mỗi lần `rxactivehs` = 1 liên tục là một burst. Byte của burst là các mẫu có `rxvalidhs` = 1 |
| Ghép với truth | Burst thứ k của một lane trong capture ghép với burst thứ k của lane đó trong truth |
| Số burst | Mỗi lane có đúng số burst của truth: không thiếu, không thừa, không burst nào còn mở lúc kết thúc |
| Payload | N byte đầu của burst thứ k bằng đúng payload của burst k trong truth, đúng thứ tự |
| Thời gian | Byte payload cuối phải tới PPI sau khi nó rời pad, và độ trễ của nó lệch khỏi trung vị của capture không quá nửa khoảng cách nhỏ nhất giữa hai burst. Luật này cần vì payload có thể lặp lại: nếu một lane mất một burst rồi thừa một burst khác, số burst và payload vẫn khớp theo thứ tự, chỉ thời gian lộ ra |
| Cờ trong burst | `rxsynchs` lên đúng một lần; `errsoths` và `errsotsynchs` không lên |
| Ngoài burst | Không có `rxvalidhs` hay cờ nào, không có giá trị X |
| Byte trailer (sau payload) | RX AMD: không giới hạn, vì IP này không cắt trailer. RX mình: tối đa theo bảng dưới |

**Giới hạn byte trailer của RX mình** theo bảng giới hạn trailer trong HAS (`doc/spec.md`, bảng 4-7). "Nhiễu 40 ns"
nghĩa là 40 ns cuối của trail là bit ngẫu nhiên, trường hợp xấu nhất mà HAS giả định cho AFE.

| Rate (Mb/s) | 260 | 400 | 600 | 800 | 1000 | 1200 | 1440 | 1500 |
|---|---|---|---|---|---|---|---|---|
| Không nhiễu | 4 | 6 | 0 | 0 | 0 | 0 | 0 | 0 |
| Nhiễu 40 ns | 4 | 6 | 7 | 8 | 9 | 10 | 12 | 12 |

**Kịch bản đạt** khi cả hai RX đều 0 lỗi.

**Khác biệt chỉ ghi nhận, không tính là lỗi:**
- số byte trailer của RX AMD;
- độ trễ của byte payload cuối;
- thời điểm `stopstate`: có ghi trong CSV nhưng không kiểm. Thứ tự giữa `stopstate` và `rxactivehs` ở cuối burst
  còn đang được chốt với team CSI-2.

## 7. Các kịch bản

Rate và số lane là tham số build. Cột plusarg chỉ ghi những gì khác mặc định.

| ID | Rate (Mb/s), lane | Plusarg | Mục đích |
|---|---|---|---|
| E1-1 | 1440, 4 | (mặc định: burst 1–1024 byte, payload `counter`) | Cơ bản, ở rate của camera |
| E1-2a | 1440, 4 | `+PATTERN=prbs9 +LENS=1,2,3,8,64,256,1024 +REPEAT=2` | Dữ liệu ngẫu nhiên |
| E1-2b | 1440, 4 | `+PATTERN=synclike +LENS=4,8,16,64,256,1024` | Sync chỉ khoá một lần, không khoá nhầm trong payload |
| E1-2c | 1440, 4 | `+UNEVEN=1 +LENS=2,3,5,9,65,257` | Lane 2–3 ít hơn 1 byte, như packet có độ dài không chia hết cho 4 |
| E1-3a | 1440, 4 | `+LENS=1,4,64,256 +PREP=min +ZERO=min` | Biên đầu burst |
| E1-3b | 1440, 4 | `+LENS=1,4,64,256 +PREP=max +ZERO=min` | Biên đầu burst |
| E1-3c | 1440, 4 | `+LENS=1,4,64,256 +TRAIL=min +EXIT=min +LPX=min` | Biên cuối burst, burst sát nhau |
| E1-3d | 1440, 4 | `+LENS=1,4,64,256 +CLK_SKEW=139` | Clock lệch 139 ps (0,2 UI) |
| E1-3e | 1440, 4 | `+LENS=1,4,64,256 +SKEW0=139 +SKEW1=139 +SKEW2=139 +SKEW3=139` | Mọi data lane lệch 139 ps |
| E1-3f | 1440, 4 | `+LENS=1,4,64,256 +SKEW1=46 +SKEW2=93 +SKEW3=139` | Các lane lệch nhau |
| E1-3g | 1440, 4 | `+LENS=1,4,64,256 +AFE=model +AFE_NOISE=1` | Nhiễu trong LP-00 trước HS. Nhiễu do `afe_model` tạo, nên chỉ RX mình chịu |
| E1-4a | 260, 4 | `+TIMEOUT_US=1500` | Rate thấp nhất mà IP AMD build được |
| E1-4a_min | 260, 4 | `+TRAIL=min +EXIT=min +LPX=min +TIMEOUT_US=1500` | Như trên, timing min |
| E1-4b | 800, 4 | — | Rate |
| E1-4c | 1500, 4 | — | Rate |
| E1-4d | 1440, 2 | — | Số lane |
| E1-4e | 1440, 1 | — | Số lane |
| E1-5 (96 run) | 260, 400, 600, 800, 1000, 1200, 1440, 1500; 4 | `+LENS=1,2,3,4,5,8,16,64,256 +REPEAT=2`, trail min/mặc định/max × `+TRAIL_JITTER=0/1` × `+EOT_JUNK=0/40`, `+CORE_HALF=2.501` | Stress cuối burst: jitter trail 0–7 bit, nhiễu cuối trail, `core_clk` lệch 400 ppm để LP-11 rơi vào mọi pha |
| `M_*` (113 run) | Như trên | Mọi kịch bản trên, thêm `+AFE=model` | Bộ phụ: RX mình sau front end giống AFE thật hơn (LP-00 trong HS) |
| R-80 | 80, 4 (`stub`) | `+LENS=1,2,3,4,5,8,16,64,256 +THS_EXIT=400` | Ngoài dải bảo đảm; chỉ báo cáo, không tính đạt hay hỏng |

Ngoài ra, `window` là một phép đo, không phải test đạt hay hỏng. Nó quét `eot_skip_bytes` từ giá trị model trừ 1 tới
cộng 2 ở 8 rate, với trail min và max, nhiễu 0 và 40 ns, 1120 burst mỗi ô, rồi [`eot_window.py`](eot_window.py) in
bảng. Các con số trong bảng giới hạn trailer ở §6 đến từ phép đo này.

## 8. Cách chạy

Chạy từ `22fdx/rx/digital`. Output của mỗi kịch bản nằm ở `fpga/work/exp1/<tên kịch bản>/`.

```bash
fpga/exp1/run_exp1.sh E1-1                 # một kịch bản cơ bản (lần đầu kèm build 1440 Mb/s, 4 lane: ~5 phút)
fpga/exp1/run_exp1.sh all                  # E1-1..E1-5, rồi bảng kết quả (~23 phút)
fpga/exp1/run_exp1.sh E1-3                 # một nhóm kịch bản
fpga/exp1/run_exp1.sh E1-5 400 600         # E1-5 ở một số rate (mỗi rate ~2,5 phút)
fpga/exp1/run_exp1.sh model                # bộ phụ M_*: mọi kịch bản, RX mình sau afe_model (~23 phút)
fpga/exp1/run_exp1.sh report               # R-80
fpga/exp1/run_exp1.sh window               # đo cửa sổ eot_skip_bytes (~7 phút)
fpga/exp1/run_exp1.sh summary              # dòng kết quả của mọi kịch bản đã chạy
python3 fpga/exp1/tn1_evidence.py          # kiểm chứng toàn bộ output (§9)
fpga/exp1/neg_front.sh                     # phép thử âm của check front end (~1 phút)
```

Muốn có đủ bộ output như lần chạy 2026-10-20 thì chạy `all`, `model`, `report` và `window`: 227 run (113 kịch bản,
113 run của bộ `M_*` và R-80), cộng 128 run của `window`. Lần chạy đó chia thành hai pha song song và xong trong 13
phút:
- pha 1: E1-1…E1-3, E1-4, R-80 với `window`, và E1-5 ở 400/600/1000/1200 Mb/s, mỗi nhóm một tiến trình;
- pha 2: E1-5 ở 260/800/1440/1500 Mb/s.

## 9. Đọc kết quả

**File của mỗi kịch bản** (`fpga/work/exp1/<tên>/`):

| File | Nội dung |
|---|---|
| `truth.txt` | Byte đã phát, theo lane và burst, kèm thời điểm |
| `xil_ppi.csv`, `ftel_ppi.csv` | PPI của RX AMD và của RX mình, định dạng ILA |
| `check.txt` | Kết quả so của `csi2_dump.py bursts` |
| `tb.txt` | Thông tin testbench in ra: timing đã dùng, front end, cấu hình RX mình, kết quả kiểm AFE |
| `xsim.log` | Log của XSIM |
| `args.txt` | Tham số của lần chạy, gồm giới hạn trailer |

**`check.txt` của E1-1 trong lần chạy 2026-10-20:**

```
A xil_ppi.csv: 4 lane(s), 40/40 bursts carry the payload sent, trailer bytes 16..17 (in 40 bursts), latency of the last payload byte 27.5..32.4 ns, errors 0
B ftel_ppi.csv: 4 lane(s), 40/40 bursts carry the payload sent, trailer bytes 0..0 (in 0 bursts), latency of the last payload byte 200.9..205.8 ns, errors 0
RESULT: PASS (A 0 errors, B 0 errors)
```

- Dòng `A` là RX AMD, dòng `B` là RX mình. Ở chế độ `stub` chỉ có một dòng, cho RX mình.
- "40/40 bursts carry the payload sent": số burst-lane có payload đúng trên tổng số. E1-1 có 10 burst × 4 lane.
- "trailer bytes 16..17 (in 40 bursts)": khoảng số byte thừa sau payload, và số burst có byte thừa.
- "latency": độ trễ từ lúc byte payload cuối rời pad tới lúc nó ra PPI.
- "errors": tổng số lỗi theo các luật ở §6. Khi có lỗi, các dòng thụt vào ngay dưới dòng `A` hoặc `B` ghi lỗi gì, ở
  lane và burst nào, ví dụ `lane 0 burst 1: 1 bytes for 2 sent, first difference at byte 1`.

**`tb.txt`:**
- `TB LINE`: timing thật đã phát (TLPX, THS-PREPARE, THS-ZERO, THS-TRAIL, THS-EXIT, TCLK-*), skew;
- `TB FRONT END`: RX mình đứng sau front end nào;
- `TB FTEL CFG`: cấu hình đã nạp cho RX mình;
- dòng `AFE`: kết quả kiểm tín hiệu bật terminal và trạng thái line;
- `TB FRONT END CHECK`: số lần đổi mà đầu ra LP của hai bộ buffer khác nhau, phải bằng 0;
- `TB DONE      OK` ở cuối: lần chạy kết thúc bình thường.

**Tổng hợp:**
- `run_exp1.sh summary` in một dòng `RESULT` cho mỗi kịch bản.
- `tn1_evidence.py` kiểm lại toàn bộ output bằng code riêng (8 check) và in `EVIDENCE: PASS (8/8 checks)` khi mọi
  check đạt. Check `margin` cần output của `window`; các check khác cần đủ bộ `all`, `model` và `report`.
- `run_exp1.sh recheck` chạy lại phần so cho mọi output mà không mô phỏng lại. Lệnh này ghi đè `check.txt`.

Kết quả mong đợi và cách hiểu các con số nằm ở [`TN1_REPORT.md`](TN1_REPORT.md).

## 10. Chạy kịch bản riêng

```bash
fpga/exp1/run_exp1.sh run 1440 4 my_test +PATTERN=prbs9 +LENS=1,8,64     # cả hai RX
fpga/exp1/run_exp1.sh run 1440 4 my_test_m +AFE=model                    # RX mình sau afe_model
fpga/exp1/run_exp1.sh run 600 stub my_stub +TRAIL=min +EOT_JUNK=40       # chỉ RX mình, rate bất kỳ
MAXTR=8 fpga/exp1/run_exp1.sh run 800 4 my_junk +EOT_JUNK=40              # cho RX mình tối đa 8 byte trailer
```

- Rate hoặc số lane mới thì script tự build trước, khoảng 5 phút.
- `MAXTR` đặt số byte trailer tối đa cho RX mình, mặc định 0.
- `+FTEL=0` giữ RX mình trong reset, để chạy riêng RX AMD.
- `+HS_SETTLE=`, `+CLK_SETTLE=`, `+EOT_SKIP=`, `+TINIT=` ghi đè cấu hình theo rate của RX mình.
- `EXP1_DEBUG=typical` giữ tín hiệu để xem waveform. Biến này cần build mới.
- Danh sách đủ plusarg (front end, timing, skew, pattern, nhiễu, seed) nằm ở đầu [`tb_exp1.sv`](tb_exp1.sv).

## 11. Bench không kiểm những gì

- **Analog:** pad chỉ là mức logic; không có jitter, ISI hay nhiễu analog. Nhiễu chỉ có ở LP-00 (E1-3g) và ở cuối trail
  (E1-5).
- **Front end:** cả hai lựa chọn đều là mô hình. Mô hình `IBUFDS_DPHY` cho LP đổi theo data trong HS, khác silicon.
  `afe_model` là AFE lý tưởng; độ giống AFE thật chỉ kiểm được trên phần cứng.
- **Metastability:** RTL chạy zero-delay. Phần này thuộc phân tích CDC và STA.
- **Phủ:** chỉ kiểm theo kịch bản, không đo functional coverage.
- **Chưa chạy:** ULPS, escape mode, deskew, non-continuous clock, packet CSI-2, lỗi bit chèn vào sync hay payload.
- **`stopstate`:** có ghi nhưng không so (§6).

## 12. Lưu ý khi đưa `ftel_dphy_rx` lên FPGA

- **Phần riêng cho ASIC** là khối AFE adapter ([`m_ftel_dphy_rx_afe_adapter.sv`](../../logical/m_ftel_dphy_rx_afe_adapter.sv))
  và các module con của nó:
  - lấy mẫu và giải nối tiếp: `m_ftel_dphy_rx_hs_deser.sv`;
  - tạo byte clock: `m_ftel_dphy_rx_byte_clk.sv`, cùng cổng đảo clock và clock gate bên trong
    (`m_ftel_dphy_rx_clk_inv.sv`, `m_ftel_dphy_rx_cg.sv`);
  - lọc nhiễu LP và phát hiện clock: `m_ftel_dphy_rx_lp_filter.sv`, `m_ftel_dphy_rx_clk_act.sv`.

  Khối này lấy mẫu bit HS trực tiếp bằng clock DDR của clock lane (720 MHz ở 1440 Mb/s) và có logic trên đường
  clock. Trong mô phỏng nó chạy đúng.
- **`core_clk`:** RTL dùng `core_clk` 200 MHz, như trong bench.
