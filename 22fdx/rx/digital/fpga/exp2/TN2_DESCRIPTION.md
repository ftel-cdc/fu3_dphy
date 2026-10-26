# TN2 — Mô tả thí nghiệm: TX của AMD phát vào `ftel_dphy_rx` và vào RX của AMD, mô phỏng XSIM

> Tài liệu cho team FPGA: lấy RTL và testbench ở đâu, hai bench gồm những gì, so theo luật nào, chạy và đọc kết quả ra
> sao. Kết quả nằm ở [`TN2_REPORT.md`](TN2_REPORT.md). TN2 có hai phần, mỗi phần một bench:
> - **TN2a** ([`fpga/exp2/`](.)): TX D-PHY của AMD phát burst vào RX D-PHY của AMD và vào `ftel_dphy_rx`;
> - **TN2b** ([`fpga/exp2b/`](../exp2b/)): CSI-2 TX Subsystem của AMD phát frame RAW10 vào hai đường nhận CSI-2 đầy
>   đủ, một trong hai đường dùng `ftel_dphy_rx`.
>
> Phiên bản 1.0, ngày 2026-10-26. Nhóm D-PHY RX viết.

## 1. Thí nghiệm làm gì

TN1 ([`../exp1/TN1_DESCRIPTION.md`](../exp1/TN1_DESCRIPTION.md)) phát vào hai RX bằng một line generator do nhóm viết.
TN2 thay nguồn phát đó bằng IP của AMD, cùng loại TX mà TN3 dùng trên board TX.

- **TN2a:** TX là IP `mipi_dphy` 4.3 của AMD, chế độ MASTER, được điều khiển ở PPI. Timing, trailer và dạng sóng trên
  pad nay là của TX AMD. Phía nhận giữ như TN1: RX AMD (`mipi_dphy` 4.3, SLAVE) và RX mình (`ftel_dphy_rx`), cùng một
  front end.
- **TN2b:** TX là CSI-2 TX Subsystem 2.2 của AMD, gồm controller CSI-2 và D-PHY TX bên trong. Frame RAW10 đi qua pad
  vào hai đường nhận:
  - **R-X (mốc):** CSI-2 RX Subsystem 6.0 của AMD, có D-PHY bên trong;
  - **R-F:** `IBUFDS_DPHY` → `ftel_dphy_rx` → khối chỉnh `rxactivehs` → CSI-2 RX Subsystem 6.0 không PHY. Đây là
    đường R-F của TN3 ([`../exp3/TN3_SPEC.md`](../exp3/TN3_SPEC.md)).

  Đây là lần đầu PPI của `ftel_dphy_rx` đi vào một controller CSI-2.

**TN2a trả lời ba câu hỏi:**
1. Khi TX AMD phát (continuous clock), hai RX có nhận đủ, đúng thứ tự, toàn bộ payload, không cờ lỗi, như ở TN1
   không?
2. Timing thật của TX, đo trên pad, nằm ở đâu so với D-PHY v1.1, và so với dải TN1 đã thử?
3. Khi TX và RX chạy từ hai nguồn clock khác nhau, như hai board ở TN3, RX mình có còn cắt trailer đúng ở mọi pha của
   `core_clk` không?

**TN2b trả lời bốn câu hỏi:**
1. Frame do TX phát có ra đúng từng pixel ở `video_out` của cả R-X lẫn R-F không? Thanh ghi lỗi của cả ba subsystem có
   sạch không?
2. Controller CSI-2 của AMD có nhận PPI của `ftel_dphy_rx` như PPI từ D-PHY của AMD không: cùng chuỗi packet, cùng bộ
   đếm, cùng trạng thái lỗi?
3. Chuỗi cấu hình theo driver và example của AMD có chạy khi byte clock của `ftel_dphy_rx` chưa chạy không? TN3 nên
   cấu hình theo thứ tự nào?
4. Cấu hình nào của ba subsystem chạy được, để dùng cho TN3?

Cả hai bench chạy trong XSIM của Vivado, không cần board.

## 2. Lấy RTL và testbench ở đâu

Repo `https://github.com/ftel-cdc/fu3_dphy`, nhánh `dev`.
- RTL `ftel_dphy_rx` (`logical/`, `config/`) là RTL TN1 đã dùng, theo HAS v0.16, không đổi từ commit `66f9f39`.
- Bench TN2a có trên nhánh từ commit `cd1f0b2`, bench TN2b từ commit `e456f21`. Khối chỉnh `rxactivehs` và hai luật
  timing ở PPI (§6.1) có trên nhánh cùng lúc với tài liệu này.

```bash
git clone -b dev https://github.com/ftel-cdc/fu3_dphy.git
cd fu3_dphy/22fdx/rx/digital          # mọi lệnh trong tài liệu này chạy từ đây
```

Đường dẫn trong bảng tính từ `22fdx/rx/digital`.

| Thành phần | Đường dẫn | Ghi chú |
|---|---|---|
| RTL `ftel_dphy_rx` | [`logical/`](../../logical/) | Như TN1: thứ tự compile ở [`logical/filelist.f`](../../logical/filelist.f), top là [`m_ftel_dphy_rx_wrap.sv`](../../logical/m_ftel_dphy_rx_wrap.sv). Không sửa gì cho mô phỏng |
| Khối chỉnh `rxactivehs` | [`fpga/rtl/m_ftel_ppi_act_gate.sv`](../rtl/m_ftel_ppi_act_gate.sv) | Chỉ dùng ở FPGA, không thuộc RTL ASIC. Nằm giữa `ftel_dphy_rx` và CSI-2 RX Subsystem không PHY, ở TN2b và ở R-F của TN3 (§5.3) |
| Kiểm riêng khối chỉnh | [`fpga/rtl/tb_m_ftel_ppi_act_gate.sv`](../rtl/tb_m_ftel_ppi_act_gate.sv), [`fpga/rtl/run_rtl.sh`](../rtl/run_rtl.sh), [`fpga/rtl/synth_rtl.tcl`](../rtl/synth_rtl.tcl) | Unit testbench, lint, kiểm luật viết RTL, synth out-of-context bằng Vivado |
| TN2a: testbench top | [`fpga/exp2/tb_exp2a.sv`](tb_exp2a.sv) | Danh sách plusarg nằm ở đầu file |
| TN2a: driver PPI của TX | [`fpga/exp2/ppi_tx_drv.sv`](ppi_tx_drv.sv) | Phát các burst qua PPI của TX AMD |
| TN2a: bộ giải mã pad | [`fpga/exp2/pad_truth.sv`](pad_truth.sv) | Giải byte, trạng thái line và timing TX từ pad, độc lập với hai RX; ghi file truth |
| TN2a: script | [`fpga/exp2/exp2.tcl`](exp2.tcl), [`fpga/exp2/run_exp2.sh`](run_exp2.sh) | Tạo IP TX (module `xtx`) và RX AMD (`xrx`) theo rate và số lane, tạo project, compile; chạy kịch bản, kiểm kết quả. Cách dùng in ở đầu `run_exp2.sh` |
| TN2a: kiểm chứng | [`fpga/exp2/tn2a_evidence.py`](tn2a_evidence.py) | Kiểm từng run (`tbcheck`), kiểm lại toàn bộ output, bảng timing TX |
| TN2b: testbench top | [`fpga/exp2b/tb_exp2b.sv`](../exp2b/tb_exp2b.sv) | Danh sách plusarg nằm ở đầu file |
| TN2b: generator frame | [`fpga/exp2b/axis_vid_gen.sv`](../exp2b/axis_vid_gen.sv) | Frame RAW10 tổng hợp trên AXI4-Stream video |
| TN2b: monitor AXI4-Stream | [`fpga/exp2b/axis_csv_mon.sv`](../exp2b/axis_csv_mon.sv) | Ghi luồng video ra CSV dạng ILA |
| TN2b: AXI4-Lite master | [`fpga/exp2b/axil_bfm.sv`](../exp2b/axil_bfm.sv) | Cấu hình và đọc thanh ghi của ba subsystem |
| TN2b: script | [`fpga/exp2b/exp2b.tcl`](../exp2b/exp2b.tcl), [`fpga/exp2b/run_exp2b.sh`](../exp2b/run_exp2b.sh) | Tạo ba subsystem theo rate, tạo project, compile; chạy kịch bản, kiểm kết quả. Cách dùng in ở đầu `run_exp2b.sh` |
| TN2b: kiểm chứng | [`fpga/exp2b/tn2b_evidence.py`](../exp2b/tn2b_evidence.py) | Kiểm từng run (`tbcheck`), kiểm lại toàn bộ output, số đo theo rate |
| Dùng lại từ TN1, không sửa | [`fpga/exp1/`](../exp1/): `afe_model.sv`, `ppi_csv_mon.sv`, `cfg_for_rate.py`, `dphy_line_gen.sv` (TN2a), `tn1_evidence.py` (bộ giải mã và model cấu hình) | Xem [`TN1_DESCRIPTION.md`](../exp1/TN1_DESCRIPTION.md) §2 và §5 |
| Bộ so | [`fpga/tools/csi2_dump.py`](../tools/csi2_dump.py) | Mode `bursts` cho TN2a, như TN1; mode `ppi` và `compare` cho TN2b. Cùng công cụ này đọc được capture ILA thật |
| Đặc tả RX mình | [`doc/spec.md`](../../doc/spec.md) | HAS của `ftel_dphy_rx` |
| Ghi chép kỹ thuật | [`fpga/exp2/README.md`](README.md), [`fpga/exp2b/README.md`](../exp2b/README.md) | Ghi chép nội bộ của nhóm D-PHY RX, chi tiết hơn tài liệu này |

## 3. Môi trường

- **Vivado 2025.2**, dùng XSIM đi kèm, như TN1 ([`TN1_DESCRIPTION.md`](../exp1/TN1_DESCRIPTION.md) §3). Biến `VIVADO`
  đổi đường dẫn của Vivado.
- **Part** `xcvp1902-vsva6865-2MP-e-S`, không cần board. Script tự tạo các IP:
  - TN2a: `mipi_dphy` 4.3, một bản MASTER (TX) và một bản SLAVE (RX AMD);
  - TN2b: MIPI CSI-2 TX Subsystem 2.2, và hai bản MIPI CSI-2 RX Subsystem 6.0 (có PHY và không PHY).

  Bench chỉ tạo IP và mô phỏng. Máy của nhóm có license Vivado; log tạo IP và mô phỏng không có thông báo license nào.
  Chưa thử trên máy không có license.
- **Python 3** có PyYAML, như TN1.
- **VCS**, chỉ cho `fpga/rtl/run_rtl.sh lint` và `sim` (khối chỉnh). Mặc định `/opt/synopsys/vcs/X-2025.06`, đổi bằng
  biến `VCS_HOME`. `run_rtl.sh synth` chỉ cần Vivado.
- **Linux, bash.**
- **Thời gian, TN2a:**
  - mỗi tổ hợp rate × số lane cần một build: lần đầu khoảng 3 phút cho Vivado và 4 phút cho compile; khi chỉ
    testbench đổi thì compile lại trong vài chục giây;
  - một run từ TX mất 85–130 s ở 4 lane và khoảng 55 s ở 1 hoặc 2 lane, vì TX cần 380–571 µs mô phỏng để khởi động;
    một run `+SRC=gen` mất 12–15 s;
  - bộ đầy đủ (60 run, 10 build) xong trong 40 phút với 3 tiến trình song song.
- **Thời gian, TN2b:**
  - mỗi rate một build (4 lane), khoảng 1 phút: Vivado khoảng 35 s, compile và elaborate khoảng 15 s;
  - một run mất 121–253 s;
  - bộ đầy đủ (40 run, 4 build) xong trong 34 phút với 3 luồng.
- **Chạy song song:**
  - TN2a: như TN1, các lệnh dùng build khác nhau chạy song song được; hai lệnh không được dùng chung một build cùng
    lúc.
  - TN2b: các run cùng build chạy song song được, vì mỗi run chép thư mục XSIM của build sang thư mục riêng. Build thì
    không được chạy cùng lúc với run trên chính build đó.
- **Bộ nhớ:** một run TN2b dùng 2,4–3,8 GB (E2b-8: 5,1 GB). Trước khi chạy 3 luồng, kiểm còn trống khoảng 15 GB.
- **Đĩa:** output nằm ở `fpga/work/exp2/` và `fpga/work/exp2b/` (git bỏ qua): khoảng 0,5 GB cho TN2a và 0,8 GB cho
  TN2b, kể cả build.

## 4. Sơ đồ

### 4.1 TN2a

```
ppi_tx_drv ─PPI─► TX AMD: mipi_dphy 4.3 MASTER ──┐
dphy_line_gen của TN1 (TX giữ reset) ────────────┴─► +SRC=tx (mặc định) hoặc +SRC=gen ─► pad, hai bản cùng giá trị
   │
   ├─► pad_truth: truth.txt (byte giải từ pad), timing TX trên pad, so byte trên pad với byte đã giao cho TX
   ├─► RX AMD: mipi_dphy 4.3 SLAVE (như TN1) ─────────────────────► PPI ─► xil_ppi.csv ───┐
   ├─► IBUFDS_DPHY (mặc định, +AFE=xil) ──┐                                               │
   │                                      ├─► ftel_dphy_rx ────────► PPI ─► ftel_ppi.csv ─┤
   └─► afe_model (+AFE=model) ────────────┘                                               │
                                csi2_dump.py bursts: mỗi CSV được so với truth.txt ◄──────┘

Kiểm trong bench: đầu ra LP của buffer bên RX AMD và của buffer trước RX mình trùng nhau ở mọi lần đổi sau 2,5 ps.
```

### 4.2 TN2b

```
axis_vid_gen: frame RAW10 tổng hợp, 4 pixel/clock ─► frames.txt
   │ AXI4-Stream video ─► tx_axis.csv
   ▼
CSI-2 TX Subsystem 2.2: controller ─PPI─► tx_ppi.csv ─► D-PHY TX bên trong (continuous clock)
   │ pad, hai bản cùng giá trị, đều strong
   ├─► R-X: CSI-2 RX Subsystem 6.0 có D-PHY ─► cổng theo dõi PPI ─► xil_ppi.csv
   │        └─► video_out ─► xil_axis.csv
   │
   └─► IBUFDS_DPHY (mặc định) hoặc afe_model ─► ftel_dphy_rx ─► PPI ─┬─► rxactivehs ─► m_ftel_ppi_act_gate ─┐
                                                                     └─► các tín hiệu PPI khác ─────────────┤
                                                            PPI vào R-F ─► ftel_ppi.csv ◄───────────────────┤
                                                            R-F: CSI-2 RX Subsystem 6.0 không PHY ◄─────────┘
                                                                 └─► video_out ─► ftel_axis.csv

So: video_out của hai RX với golden, từng pixel; packet trên ba PPI; thanh ghi của ba subsystem, đọc qua AXI4-Lite.
Kiểm trong bench: đầu ra LP của buffer trong D-PHY của R-X và của buffer trước RX mình trùng nhau ở mọi lần đổi sau
2,5 ps.
```

## 5. Các khối của bench

### 5.1 TN2a ([`fpga/exp2/`](.))

**TX AMD** (module `xtx`, tạo bởi [`exp2.tcl`](exp2.tcl)):
- IP `mipi_dphy` 4.3, MASTER, SupportLevel 1, cùng rate và cùng số lane với RX AMD (`xrx`).
- `C_INIT` 99 µs, mức nhỏ nhất của IP. Các tham số khác để mặc định, ví dụ `C_LPX_PERIOD` 50 ns (TLPX đo trên pad là
  55 ns) và `C_USE_LANE0_TXREADYHS` true (`txreadyhs` của lane 0 điều khiển mọi lane).
- Continuous clock không phải tham số của IP: driver giữ `cl_txrequesths` = 1, như example của AMD.
- Timing HS (PREPARE, ZERO, TRAIL, EXIT và các TCLK) do IP tự tính theo rate, không chỉnh được. Bench đo chúng trên
  pad.
- Pad: `OBUFDS_DPHY` lái strong trong LP và supply trong HS. Cả hai đều là strength "S", nên `IBUFDS_DPHY` của hai RX
  vẫn thấy cùng loại front end như ở TN1.
- Hai điều đo được khi dựng bench:
  - TX báo `init_done` sau 380–571 µs tuỳ rate, dù `C_INIT` = 99 µs;
  - model clock của TX cho line đúng rate danh định, bất kể chu kỳ `core_clk` của TX. Vì vậy, muốn line lệch so với
    RX thì phải lệch `core_clk` của RX (`+CORE_HALF`), như TN1.

**Driver PPI** ([`ppi_tx_drv.sv`](ppi_tx_drv.sv)), chạy theo `txbyteclkhs` của TX:
- khởi động clock lane: đặt `cl_txrequesths` = 1, chờ `cl_txclkactivehs`, rồi chờ thêm 2 µs như TN1;
- mỗi burst: mọi lane có byte cùng bật `txrequesths`, kèm byte đầu. Ở mỗi cạnh có `txreadyhs` = 1, lane đó nhận byte
  kế; lane nhận byte cuối thì hạ request. Sau đó driver chờ mọi lane về `stopstate`, rồi chờ thêm `+GAP_NS` (mặc định
  150 ns);
- đếm số burst đã xong và số lane burst không vào HS;
- `+TX_CORRUPT=<lane>,<burst>,<byte>`: phát byte đó đảo bit, nhưng vẫn ghi giá trị gốc làm dự kiến. Chỉ dùng cho phép
  thử âm NEG-tx.

**Bộ giải mã pad** ([`pad_truth.sv`](pad_truth.sv)), độc lập với cả hai RX và với `afe_model`:
- tự tính trạng thái line từ pad, và so với trạng thái `afe_model` suy ra ở mỗi lần đổi;
- lấy mẫu `d_p` ở cả hai cạnh của clock trên pad khi clock lane và data lane đều ở HS, và khoá sync ở lần đầu 8 bit
  cuối bằng 0xB8;
- ghi mỗi lane burst vào `truth.txt`, cùng format với truth của line generator TN1, nên `csi2_dump.py bursts` đọc được
  như ở TN1. Thời điểm t0 là đầu byte sync, t1 là cuối bit payload cuối;
- so byte trên pad với byte đã giao cho TX. Byte khác, burst thừa, burst thiếu, burst không có sync hay thiếu byte đều
  là lỗi;
- đo timing của TX trên pad và so với giới hạn của D-PHY v1.1 ở rate đó: TLPX, THS-PREPARE, THS-ZERO, THS-TRAIL,
  THS-EXIT của mỗi data lane; TLPX, TCLK-PREPARE, TCLK-ZERO, TCLK-PRE của clock lane. Phần này chỉ báo cáo.

**Testbench** ([`tb_exp2a.sv`](tb_exp2a.sv)):
- Front end của RX mình, check front end và instance `m_ftel_dphy_rx_wrap` được lấy nguyên văn từ
  [`tb_exp1.sv`](../exp1/tb_exp1.sv). Check `copy` của `tn2a_evidence.py` so lại ba khối này với TN1 ở mỗi lần kiểm
  chứng.
- Pad có hai bản cùng giá trị, đều lái bằng `assign` nên đều strong: một bản vào RX AMD và `pad_truth`, một bản vào
  front end của RX mình và `afe_model`.
- `+SRC=tx|gen` chọn nguồn của pad: TX AMD (mặc định) hoặc line generator của TN1. Với `gen`, TX bị giữ reset, và truth
  của generator được ghi riêng vào `truth_gen.txt` để kiểm `pad_truth` (E2a-0).
- Check front end như TN1, nhưng chỉ tính các lần so sau 2,5 ps. Pad của TX rời X ở 1 ps, nên lần so các giá trị khởi
  tạo có thể rơi đúng lúc hai buffer đang đổi. Các lần so trước 2,5 ps vẫn được in ra, ở dòng
  `TB FRONT END CHECK START`.
- `+NEG_FRONT=1`: trong HS, bản pad vào RX mình mang strength pull. Đây là phép thử âm của check front end.
- **Trình tự một run:**
  1. nhả reset;
  2. chờ `init_done` của TX, của RX AMD và của RX mình;
  3. bật monitor, khởi động clock lane;
  4. phát các burst; mỗi burst được ghi vào `expected.txt` trước khi phát;
  5. chờ delay line của RX mình xả hết, rồi in kết quả.

**Phía nhận** như TN1: RX AMD (`mipi_dphy` 4.3, SLAVE); RX mình sau `IBUFDS_DPHY` hoặc `afe_model`, cấu hình theo rate
bằng [`cfg_for_rate.py`](../exp1/cfg_for_rate.py); monitor PPI [`ppi_csv_mon.sv`](../exp1/ppi_csv_mon.sv)
([`TN1_DESCRIPTION.md`](../exp1/TN1_DESCRIPTION.md) §5).

### 5.2 TN2b ([`fpga/exp2b/`](../exp2b/))

**Ba subsystem**, tạo bởi [`exp2b.tcl`](../exp2b/exp2b.tcl), mỗi rate một build, 4 lane. `exp2b.tcl` in một dòng
`EXP2B` với tham số của từng IP, và check `config` của `tn2b_evidence.py` so các dòng đó với bảng dưới.

| IP | Module | Cấu hình |
|---|---|---|
| CSI-2 TX Subsystem 2.2 | `xtxss` | 4 lane, RAW10, 4 pixel/clock, `C_CSI_MAX_BPC` 10, AXI4-Stream, Active Lanes, CRC, `C_HS_LINE_RATE` = rate, `C_INC_PHY` true (D-PHY MASTER bên trong), `SupportLevel` 1. Còn lại để mặc định: line buffer 2048, `C_EN_REG_BASED_FE_GEN` false, LPX 50 ns, không deskew |
| CSI-2 RX Subsystem 6.0 có PHY | `xrxss` (R-X) | Như build bring-up của board: 4 lane, RAW10, 4 pixel/clock, `CSI_BUF_DEPTH` 16384, CRC, Active Lanes, lọc user data type, frame buffer (VFB) với `VFB_TU_WIDTH` 96, `SupportLevel` 1. Thêm `C_EN_RXPPI_AS_MON` (cổng theo dõi PPI). `DPY_LINE_RATE` = `C_HS_LINE_RATE` = rate |
| CSI-2 RX Subsystem 6.0 không PHY | `xrxss_np` (R-F) | Như R-X, nhưng `C_INC_PHY` false và không có cổng theo dõi PPI |

HS settle do IP tự chọn theo rate (`C_HS_SETTLE_NS`): 173 ns ở 260 Mb/s, 147 ns ở 800, 141 ns ở 1440 và 1500. `C_INIT`
của D-PHY trong R-X là 100 µs.

**Nối R-F** (instance `u_xrxss_np` trong `tb_exp2b.sv`):

| Cổng của RX Subsystem không PHY | Nối với |
|---|---|
| `rxbyteclkhs_in` | `o_dphy_rx_rxbyteclkhs` của `ftel_dphy_rx` |
| `dphy_clk_200M` | `core_clk` 200 MHz, chung với `ftel_dphy_rx` và R-X |
| `mipi_ppi_if_dl<n>_rxactivehs` | `o_rxactivehs` của khối chỉnh (§5.3) khi đặt `+PPI_ADAPTER=1`, như ở mọi run `SH_*`; nếu không thì thẳng từ `ftel_dphy_rx` |
| `mipi_ppi_if_dl<n>_rxdatahs`, `_rxvalidhs`, `_rxsynchs`, `_stopstate`, `_errsoths`, `_errsotsynchs`, `_errcontrol`, `_erresc`, `_rxulpsesc`; `mipi_ppi_if_cl_stopstate`, `_cl_rxulpsclknot` | Thẳng từ các chân cùng tên của `ftel_dphy_rx` |
| `mipi_ppi_if_cl_enable`, `mipi_ppi_if_dl<n>_enable` (do controller lái) | `i_dphy_rx_cl_enable`, `i_dphy_rx_dl_enable` của `ftel_dphy_rx`. TN1 buộc hai chân này bằng 1 |
| (không có) | `i_dphy_rx_forcerxmode` của `ftel_dphy_rx` buộc 0 |

**Generator** ([`axis_vid_gen.sv`](../exp2b/axis_vid_gen.sv)):
- frame tổng hợp, 4 pixel mỗi beat (pixel k ở `tdata[10k+9:10k]`), tôn trọng `tready`;
- `tuser` như example của TX Subsystem: bit 0 là SOF ở beat đầu frame, bit 32:1 là data type (0x2B), bit 63:48 là word
  count của line. `tlast` ở beat cuối mỗi line; `tdest` = 0 (VC 0);
- ghi `frames.txt` trước beat đầu của mỗi frame.

Pixel được tính theo công thức, nên mỗi pixel mang vị trí của nó, và lệch, đảo lane, lẫn line hay mất line đều lộ ra
kèm vị trí. Đây không phải ảnh mẫu hay frame camera.

| Pattern | Pixel p(f, y, x) của frame f, line y, cột x | Bắt được gì |
|---|---|---|
| `counter` (mặc định) | (x + 37·y + 101·f) mod 1024 | lệch hay đổi chỗ pixel, lẫn line, lẫn frame |
| `prbs` | 10 bit liên tiếp của LFSR x¹⁵ + x¹⁴ + 1, seed 1 + f·H + y | lỗi phụ thuộc dữ liệu |
| `synclike` | lặp 0x2E0 0x2E0 0x000 0x000 0x3FF 0x3FF 0x155 0x2AA | byte 0xB8 giống sync, chuỗi 0x00/0xFF, 0x55/0xAA |

Trên dây, TX đóng gói 4 pixel RAW10 thành 5 byte (CSI-2 v1.3); RX mở gói ở `video_out`.

**Monitor:**
- [`axis_csv_mon.sv`](../exp2b/axis_csv_mon.sv): CSV dạng ILA, một dòng cho mỗi clock có `tvalid`, ở ba luồng: đầu vào
  của TX (`tx_axis.csv`) và `video_out` của hai RX (`xil_axis.csv`, `ftel_axis.csv`). Ở `video_out` có thêm các trường
  của `tuser`: frame, line, word count, data type. Không có cột lỗi packet: với dữ liệu pixel, frame buffer của RX
  Subsystem luôn đặt `tuser[1]` = 0 ([`TN2_REPORT.md`](TN2_REPORT.md) §4.7).
- [`ppi_csv_mon.sv`](../exp1/ppi_csv_mon.sv) của TN1, ba bản: trên cổng theo dõi PPI của R-X (`xil_ppi.csv`), trên PPI
  vào R-F (`ftel_ppi.csv`), và trên PPI giữa controller và D-PHY bên trong TX (`tx_ppi.csv`).

**AXI4-Lite master** ([`axil_bfm.sv`](../exp2b/axil_bfm.sv)): `wr`, `rd`, `poll`; mỗi bắt tay có giới hạn thời gian,
và `resp` được kiểm. Ba instance, cho TX, R-X và R-F. Mỗi truy cập in một dòng `TB AXIL`.

**Testbench** ([`tb_exp2b.sv`](../exp2b/tb_exp2b.sv)):
- Lấy từ [`tb_exp1.sv`](../exp1/tb_exp1.sv): front end của RX mình, nguyên văn; check front end, khác đúng dòng đường
  dẫn (nay so với buffer trong D-PHY của R-X); instance `m_ftel_dphy_rx_wrap`, khác đúng 6 dòng của bảng nối. Check
  `copy` của `tn2b_evidence.py` kiểm đúng các dòng khác này ở mỗi lần kiểm chứng.
- **Thứ tự cấu hình:**
  - RX, theo driver của AMD: soft reset, chờ `CSR[0]`, đặt active lanes, nhả soft reset, `GIER`, enable;
  - TX, như example của TX Subsystem: đặt active lanes, `CCR` = 1 (enable; `CCR[4]` = 0 là continuous clock), chờ
    `CCR[2]` (core ready), rồi phát video ngay;
  - mặc định, hai RX được cấu hình trước khi TX chạy, như example camera của AMD, tức lúc chưa có byte clock.
- **Clock:** `core_clk` 200 MHz (hai RX và `ftel_dphy_rx`); core clock riêng 200 MHz của TX; `s_axis_aclk` 200 MHz của
  TX, cũng là clock AXI4-Lite của TX như trong example; `video_aclk` 250 MHz của hai RX; `lite_aclk` 50 MHz.
- **Can thiệp trên PPI vào R-F**, đặt trước monitor, nên `ftel_ppi.csv` ghi đúng những gì R-F nhận:
  - `+PPI_CORRUPT=<lane>,<packet>,<byte>,<bit>`: lật một bit, cho phép thử âm. Packet đếm burst của lane đó từ 0, byte
    đếm byte của burst từ 0;
  - `+PPI_ADAPTER=1`: `rxactivehs` vào R-F lấy từ khối chỉnh (§5.3). Testbench có model riêng của luật đó, so với khối
    ở mọi byte clock, và in `TB ADAPTER CHECK: comparisons N, differences D`;
  - `+PPI_SOTSYNCERR=<lane>,<packet>` (E2b-9): ở burst đó, bỏ `rxsynchs` và `rxvalidhs`, đặt `errsotsynchs` vào chu kỳ
    của `rxsynchs`. Đó là PPI của `ftel_dphy_rx` sau một lỗi SoT sync, theo HAS (bảng A-2). Run kết thúc khi 30 µs
    không RX nào ra line;
  - chỉ để chẩn đoán: `+PPI_XFILL=1` (bit X hoặc Z của `rxdatahs` thành 0) và `+PPI_AMD_TIMING=1|2|3` (dời đầu burst về
    kiểu của D-PHY AMD). Hai cờ này đã dùng để tìm ra phát hiện ở [`TN2_REPORT.md`](TN2_REPORT.md) §4.1.

    | `+PPI_AMD_TIMING` | `rxsynchs` | `rxactivehs` | Dữ liệu, `rxvalidhs` |
    |---|---|---|---|
    | 0 (mặc định) | cùng chu kỳ với byte đầu, như HAS | sớm hơn `rxsynchs` | như `ftel_dphy_rx` |
    | 1 | trước byte đầu 1 chu kỳ | từ `rxsynchs` | trễ 1 chu kỳ |
    | 2 | trước byte đầu 1 chu kỳ | sớm như mode 0 | trễ 1 chu kỳ |
    | 3 | cùng chu kỳ với byte đầu | từ `rxsynchs` | như mode 0 |

- `+RX_LATE=1`: cấu hình hai RX khi đã phát nửa frame 0. `+STREAM_TOGGLE=1`: tắt TX sau frame 0 rồi bật lại.
- Danh sách đủ plusarg nằm ở đầu file.

### 5.3 Khối chỉnh `rxactivehs` ([`fpga/rtl/m_ftel_ppi_act_gate.sv`](../rtl/m_ftel_ppi_act_gate.sv))

**Vì sao có khối này.** Ở đầu mỗi burst, `ftel_dphy_rx` nâng `rxactivehs` trước `rxsynchs` vài byte clock (7 ở
260 Mb/s, 19–20 ở 1440 Mb/s), và đưa `rxsynchs` cùng chu kỳ với byte đầu. HAS cho phép như vậy. D-PHY của AMD nâng hai
tín hiệu cùng lúc, byte đầu ở chu kỳ sau. Controller CSI-2 của AMD không nhận packet nào khi `rxactivehs` lên trước
`rxsynchs` ([`TN2_REPORT.md`](TN2_REPORT.md) §4.1). Khối này sửa điều đó ở FPGA, không đụng RTL ASIC và không đổi
hợp đồng PPI của `ftel_dphy_rx` với controller CSI-2 của chip.

**Chức năng, ở mỗi lane:** `o_rxactivehs = i_rxactivehs & (i_rxsynchs | reg_seen)`, với `reg_seen` là giá trị
`o_rxactivehs` ở chu kỳ trước.
- `rxactivehs` ra lên cùng `rxsynchs` đầu tiên của burst và giữ tới hết burst.
- Burst không có `rxsynchs` (lỗi SoT sync) giữ `rxactivehs` ra ở 0.
- Burst bắt đầu ngay sau một chu kỳ `rxactivehs` = 0 vẫn chờ `rxsynchs` của chính nó.
- Không thêm trễ. Mọi tín hiệu PPI khác, kể cả `errsotsynchs`, đi thẳng vào RX Subsystem, không qua khối.

| Port | Hướng | Nối với |
|---|---|---|
| `PARA_NUM_LANES` | tham số | số data lane, mặc định 4 |
| `i_byte_clk` | vào | `o_dphy_rx_rxbyteclkhs` của `ftel_dphy_rx` |
| `i_byte_rst_n` | vào | cùng reset với `ftel_dphy_rx` (`i_dphy_rx_phy_core_rst_n`), tích cực mức thấp |
| `i_rxactivehs[NL-1:0]` | vào | `o_dphy_rx_rxactivehs` của `ftel_dphy_rx` |
| `i_rxsynchs[NL-1:0]` | vào | `o_dphy_rx_rxsynchs` của `ftel_dphy_rx` (chân này cũng đi thẳng vào RX Subsystem) |
| `o_rxactivehs[NL-1:0]` | ra | `rxactivehs` của từng lane ở RX Subsystem không PHY |

- **Reset:** khối có bộ đồng bộ reset riêng, 2 flip-flop có `ASYNC_REG`. Reset vào ngay khi `i_byte_rst_n` xuống, và
  nhả ở cạnh thứ hai của byte clock. Byte clock của `ftel_dphy_rx` dừng khi clock lane không ở HS; khi đó việc nhả
  reset chờ byte clock chạy, và `ftel_dphy_rx` cũng không đưa `rxactivehs` khi chưa có byte clock.
- **Kích thước:** 6 flip-flop và 6 LUT với 4 lane. Synth out-of-context trên part của board ở 224 MHz: WNS +1,089 ns.
- **Port khai báo `input var logic`:** với `` `default_nettype none ``, Vivado synth và XSIM khi không có `--relax`
  không nhận port `input logic` (lỗi VRFC 10-1103).
- **Kiểm riêng** (`fpga/rtl/run_rtl.sh`, output ở `fpga/work/rtl/`): lint VCS với 1, 2 và 4 lane; kiểm luật viết RTL;
  unit testbench VCS có model riêng, với burst ngẫu nhiên và burst có hướng, 1, 2 và 4 lane; synth Vivado
  out-of-context. Kết quả ở [`TN2_REPORT.md`](TN2_REPORT.md) §4.2.

## 6. Luật so và tiêu chí đạt

### 6.1 TN2a

**`check.txt`** (`csi2_dump.py bursts`) so mỗi CSV với `truth.txt` theo đúng các luật của TN1
([`TN1_DESCRIPTION.md`](../exp1/TN1_DESCRIPTION.md) §6): số burst, payload, thời gian, cờ trong burst, ngoài burst,
byte trailer. Hai luật timing ở PPI có từ 2026-10-26, theo HAS (bảng A-2):
- ở mỗi lane burst, `rxsynchs` High đúng một mẫu: cùng chu kỳ với byte payload đầu ở RX mình, trước byte đầu một chu kỳ
  ở RX AMD;
- trong mỗi burst, byte thứ k tới PPI trên các lane lệch nhau tối đa 6 byte clock.

**Khác TN1:**
- Truth giải từ pad (`pad_truth`), không lấy từ nguồn phát. Nhờ vậy cùng một cách lấy truth dùng được cho cả TX AMD lẫn
  line generator.
- `pad_truth` được kiểm bằng chính line generator của TN1 (E2a-0): truth giải từ pad phải trùng truth của generator từng
  byte, t0 và t1 lệch không quá 1 ps.
- Giới hạn byte trailer của RX mình lấy theo HAS (bảng 4-7, không nhiễu): 4 byte ở 260 Mb/s, 6 ở 400, 0 từ 600 Mb/s. RX
  AMD không giới hạn.

**`tbcheck.txt`** (`tn2a_evidence.py tbcheck`), mỗi mục một dòng:

| Mục | Đạt khi |
|---|---|
| `done` | run kết thúc bằng `TB DONE OK` |
| `pads` | `pad_truth` giải đủ mọi lane burst trong `expected.txt`, không thừa, có sync, đủ byte; 0 byte khác; trạng thái line trùng `afe_model` ở mọi lần đổi |
| `front` | đầu ra LP của hai bộ buffer trùng nhau ở mọi lần đổi sau 2,5 ps; có dòng `TB FRONT END CHECK START` |
| `afe` | `afe_model` không báo lỗi trạng thái; `term_en` không trễ, không thiếu |
| `tx` | (nguồn là TX) TX làm xong mọi burst, và mọi lane burst đều rời `stopstate` |
| `padtruth` | (nguồn là generator) `truth.txt` trùng `truth_gen.txt` |

**Một run đạt** khi cả `check.txt` lẫn `tbcheck.txt` đạt.

**Chỉ ghi nhận, không tính là lỗi:** số byte trailer của RX AMD, độ trễ của byte payload cuối, thời điểm `stopstate`,
và timing của TX (có nhãn `OUTSIDE` nếu ra ngoài giới hạn của D-PHY v1.1).

### 6.2 TN2b

**Golden.** Ba bản phải trùng nhau trước, rồi hai RX mới được so với chúng:
1. công thức pixel, viết lại riêng trong `tn2b_evidence.py`;
2. `frames.txt`: những gì generator đưa ra;
3. `tx_axis.csv`: những beat TX thực sự nhận (`tvalid` và `tready`).

**`check.txt`** (`csi2_dump.py`), 7 mục:

| Mục | Lệnh `csi2_dump.py` | Đạt khi |
|---|---|---|
| `pixels-xil` | `compare axis tx_axis.csv xil_axis.csv` | `video_out` của R-X trùng từng pixel với các beat TX đã nhận, cùng số line |
| `pixels-ftel` | `compare axis tx_axis.csv ftel_axis.csv` | như trên, cho R-F |
| `ppi-tx` | `ppi tx_ppi.csv` | PPI bên trong TX: mọi packet đúng ECC và CRC |
| `ppi-xil` | `ppi xil_ppi.csv` | PPI của R-X: đúng ECC và CRC; `rxsynchs` trước byte đầu một chu kỳ; lệch giữa các lane tối đa 6 byte clock |
| `ppi-ftel` | `ppi ftel_ppi.csv` | PPI vào R-F: đúng ECC và CRC; `rxsynchs` cùng chu kỳ với byte đầu; lệch giữa các lane tối đa 6 byte clock |
| `packets-tx-xil` | `compare ppi tx_ppi.csv xil_ppi.csv` | cùng chuỗi packet: VC, data type, word count, payload |
| `packets-xil-ftel` | `compare ppi xil_ppi.csv ftel_ppi.csv` | như trên, giữa R-X và R-F |

Một phép so chỉ đạt khi hai bên có cùng số line hoặc packet. Với `+RX_LATE=1` (E2b-6), frame của TX được so từ SOF thứ
hai, frame của mỗi RX từ SOF đầu tiên sau khi RX đó được cấu hình, và mục `packets-tx-xil` không chạy.

**`tbcheck.txt`** (`tn2b_evidence.py tbcheck`):

| Mục | Đạt khi |
|---|---|
| `done` | run kết thúc bằng `TB DONE OK` |
| `axil` | mọi truy cập AXI4-Lite của ba master xong trong giới hạn thời gian, với `resp` OKAY |
| `tx` | TX lên core ready (`CCR[2]`), phát đủ số frame và line, ISR của TX không có cờ lỗi |
| `regs` | ISR của hai RX có frame received và không cờ lỗi; R-F có packet count và image info của VC0 bằng R-X; word count và data type đúng frame đã phát |
| `axis` | ba luồng AXI4-Stream (TX, R-X, R-F) có đúng số line và số frame |
| `front` | như TN2a, so với buffer trong D-PHY của R-X |
| `afe` | `term_en` không trễ, không thiếu |
| `corrupt` | (với `+PPI_CORRUPT`) đúng một byte bị lật |
| `adapter` | (với `+PPI_ADAPTER=1`) khối chỉnh trùng model của testbench ở mọi byte clock |
| `sotsync` | (với `+PPI_SOTSYNCERR`) đúng một burst đã định mang lỗi SoT sync |

**Một run đạt** khi cả `check.txt` lẫn `tbcheck.txt` đạt. Chuẩn là từng pixel bằng nhau tuyệt đối, đúng số line, mỗi
frame đúng một SOF, đúng thứ tự frame.

**Ngoại lệ:**
- E2b-6 và E2b-8: thanh ghi của hai RX chỉ báo cáo, vì frame đầu bị cắt (cấu hình muộn) hoặc thiếu FE (tắt luồng).
- E2b-9: phần của R-F trong `check.txt` hỏng theo thiết kế; `tbcheck` phải đạt, và check `gate` của `tn2b_evidence.py`
  chấm phần còn lại ([`TN2_REPORT.md`](TN2_REPORT.md) §4.5).

**Chỉ ghi nhận, không tính là lỗi:** số byte trailer trên PPI, độ trễ, thời điểm khởi động TX, và giá trị X ở các bit
dự trữ của ISR.

## 7. Các kịch bản

### 7.1 TN2a

Payload mặc định như E1-1 của TN1: độ dài 1, 2, 3, 4, 5, 8, 16, 64, 256, 1024 byte, mỗi độ dài một lần, mẫu `counter`.
Rate và số lane là tham số build. Cột plusarg chỉ ghi những gì khác mặc định.

| ID | Rate (Mb/s), lane | Plusarg | Mục đích |
|---|---|---|---|
| E2a-0a | 1440, 4 | `+SRC=gen` | Kiểm `pad_truth` bằng line generator, với các độ dài của E1-1 |
| E2a-0b | 1440, 4 | `+SRC=gen +LENS=1,4,64,256 +TRAIL=min +EXIT=min +LPX=min` | Như trên, ở góc timing của E1-3c |
| E2a-0c | 1440, 4 | `+SRC=gen +UNEVEN=1 +LENS=2,3,5,9,65,257` | Như trên, các lane kết thúc lệch nhau |
| E2a-1 | 1440, 4 | — | Cơ bản. RX AMD phải đạt trước, để chứng minh hookup TX và truth |
| E2a-2a | 1440, 4 | `+PATTERN=prbs9 +LENS=1,2,3,8,64,256,1024 +REPEAT=2` | Dữ liệu ngẫu nhiên |
| E2a-2b | 1440, 4 | `+PATTERN=synclike +LENS=4,8,16,64,256,1024` | Payload có mẫu giống sync |
| E2a-2c | 1440, 4 | `+UNEVEN=1 +LENS=2,3,5,9,65,257` | Lane 2–3 ít hơn 1 byte, lane 0 dài nhất |
| E2a-3 | 1440, 4 | `+GAP_NS=0 +LENS=1,4,64,256 +REPEAT=2` | Burst kế được request ngay khi về `stopstate`: THS-EXIT nhỏ nhất của TX |
| E2a-4a | 260, 4 | `+TIMEOUT_US=3000`; trailer RX mình tối đa 4 | Rate thấp nhất của TX |
| E2a-4b, E2a-4c | 800, 1500; 4 | — | Rate bring-up của TN3; rate cao nhất của dải bảo đảm |
| E2a-4d, E2a-4e | 1440; 2, 1 | — | Số lane |
| E2a-5 (16 run) | 260, 400, 600, 800, 1000, 1200, 1440, 1500; 4 | `+LENS=1,2,3,4,5,8,16,64,256 +REPEAT=6`; `+CORE_HALF=2.501` (run `_slow`) và `2.499` (run `_fast`); trailer RX mình theo bảng 4-7 | EoT với trail thật của TX; `core_clk` của hai RX lệch ±400 ppm để LP-11 rơi vào mọi pha |
| `M_*` (29 run) | Như trên | Mọi kịch bản trên, thêm `+AFE=model` | Bộ phụ: RX mình sau `afe_model` (LP-00 trong HS, như silicon) |
| NEG-tx | 1440, 4 | `+TX_CORRUPT=1,3,0` | Phép thử âm: check byte trên pad phải báo đúng 1 byte khác, run phải hỏng, trong khi hai RX vẫn khớp pad |
| NEG-front | 1440, 4 | `+NEG_FRONT=1` | Phép thử âm: check front end phải đếm ra khác biệt |

Mỗi run E2a-5 có 54 burst, tức 216 lane burst. Hai chiều lệch cộng lại là 432 lane burst mỗi rate, bằng một ô E1-5 của
TN1.

### 7.2 TN2b

Mặc định: 2 frame 640 × 16 (word count 800 byte), mẫu `counter`, 1440 Mb/s, 4 lane.

| ID | Rate (Mb/s), lane | Plusarg | Mục đích |
|---|---|---|---|
| E2b-1 | 1440, 4 | — | Cơ bản |
| E2b-2a, E2b-2b | 1440, 4 | `+PATTERN=prbs`, `+PATTERN=synclike` | Payload ngẫu nhiên; payload có byte giống sync |
| E2b-2c | 1440, 4 | `+WIDTH=3840 +HEIGHT=8` | Line dài cỡ sensor 4K (word count 4800) |
| E2b-3 | 1440, 4 | `+FRAMES=8 +WIDTH=64 +HEIGHT=4` | FS và FE dày, packet sát nhau |
| E2b-4a, E2b-4b, E2b-4c | 260, 800, 1500; 4 | như E2b-1 (260: `+TIMEOUT_US=8000`) | Rate thấp nhất; rate bring-up của TN3; rate cao nhất của dải bảo đảm |
| E2b-5a, E2b-5b | 1440; build 4 lane, 2 và 1 lane active | `+LANES_ACTIVE=2`, `+LANES_ACTIVE=1` | Đổi số lane không cần build lại |
| E2b-6 | 1440, 4 | `+FRAMES=4 +RX_LATE=1` | RX được cấu hình giữa frame 0; so từ SOF kế tiếp; thanh ghi chỉ báo cáo |
| E2b-7a, E2b-7b | 1440, 4 | như E2b-3, thêm `+CORE_HALF=2.501`, `+CORE_HALF=2.499` | ±400 ppm giữa TX và hai RX |
| E2b-8 | 1440, 4 | `+FRAMES=4 +STREAM_TOGGLE=1` | Tắt rồi bật lại TX sau frame 0; thanh ghi chỉ báo cáo |
| E2b-9 | 1440, 4 | `+FRAMES=3 +PPI_SOTSYNCERR=0,5` (lane 0, packet 5, tức line 4 của frame 0); chỉ chạy qua khối chỉnh | Lỗi SoT sync ở một lane: controller không được treo, và các frame sau phải đúng |
| `M_*` (13 run) | như trên | mọi kịch bản trên trừ E2b-8 và E2b-9, thêm `+AFE=model` | RX mình sau `afe_model` |
| NEG-ecc | 1440, 4 | `+PPI_CORRUPT=0,1,0,0` (bit 0 của byte header đầu, packet 1) | Phép thử âm: lỗi ECC sửa được; chỉ thanh ghi ECC của R-F báo |
| NEG-crc | 1440, 4 | `+PPI_CORRUPT=1,1,2,3` (một bit payload) | Phép thử âm: lỗi CRC, đúng một pixel sai |
| NEG-front | 1440, 4 | `+NEG_FRONT=1` | Phép thử âm: check front end phải đếm ra khác biệt |

**Hai nhóm run** (`run_exp2b.sh`), tổng 40 run:
- **`SH_*`** (`run_exp2b.sh shim`, 31 run): 15 kịch bản, 13 run `M_*` và 3 phép thử âm, tất cả với `rxactivehs` vào R-F
  qua khối chỉnh (`+PPI_ADAPTER=1`). Đây là tập được chấm.
- **Phát hiện** (`run_exp2b.sh finding`, 9 run): E2b-1, E2b-4a, E2b-4b, E2b-4c và E2b-6 không có khối chỉnh, cùng 4 run
  chẩn đoán `DBG-E2b-1-xfill`, `DBG-E2b-1-amd1`, `DBG-E2b-1-amd2`, `DBG-E2b-1-amd3`. Nhóm này cho thấy vì sao cần khối
  chỉnh ([`TN2_REPORT.md`](TN2_REPORT.md) §4.1).

## 8. Cách chạy

Chạy từ `22fdx/rx/digital`. Output của mỗi kịch bản nằm ở `fpga/work/exp2/<tên>/` (TN2a) hoặc
`fpga/work/exp2b/<tên>/` (TN2b).

**TN2a:**

```bash
fpga/exp2/run_exp2.sh E2a-1                # cơ bản, 1440 Mb/s, 4 lane (~1,5 phút, lần đầu thêm ~7 phút build)
fpga/exp2/run_exp2.sh all                  # E2a-0 tới E2a-5, rồi bảng kết quả
fpga/exp2/run_exp2.sh E2a-5 400 600        # E2a-5 ở một số rate (mỗi rate 2 run, ~4 phút)
fpga/exp2/run_exp2.sh E2a-4 a b            # một phần của E2a-4
fpga/exp2/run_exp2.sh model                # bộ phụ M_*: mọi kịch bản, RX mình sau afe_model
fpga/exp2/run_exp2.sh model E2a-5 1440     # bộ phụ, một nhóm hoặc một số rate
fpga/exp2/run_exp2.sh neg                  # NEG-tx và NEG-front
fpga/exp2/run_exp2.sh summary              # dòng kết quả (check.txt | tbcheck.txt) của mọi run
fpga/exp2/run_exp2.sh recheck              # kiểm lại mọi output bằng công cụ hiện tại, không mô phỏng (~6 s)
fpga/exp2/run_exp2.sh txtiming             # bảng timing TX trên pad theo rate, kèm giới hạn D-PHY v1.1
fpga/exp2/run_exp2.sh evidence             # kiểm chứng toàn bộ output (§9)
python3 fpga/exp2/tn2a_evidence.py evselftest   # thử chính script kiểm chứng trên các lỗi cài sẵn (§9)
```

Bộ đầy đủ là `all`, `model` và `neg`: 60 run (29 kịch bản, 29 run `M_*`, 2 phép thử âm), 10 build. Lần chạy
2026-10-22 dùng 3 tiến trình, mỗi tiến trình giữ riêng các build của mình, và xong trong 40 phút.

**TN2b:**

```bash
fpga/exp2b/run_exp2b.sh build 1440         # ba subsystem, project, compile, elaborate (~1 phút)
fpga/exp2b/run_exp2b.sh shim               # 31 run SH_*: mọi kịch bản (cả E2b-9), M_* và phép thử âm, qua khối chỉnh
fpga/exp2b/run_exp2b.sh shim E2b-4 a       # một phần, qua khối chỉnh
fpga/exp2b/run_exp2b.sh shim E2b-9         # lỗi SoT sync ở lane 0 của packet 5
fpga/exp2b/run_exp2b.sh finding            # 9 run của phát hiện: không có khối chỉnh, và các run chẩn đoán
fpga/exp2b/run_exp2b.sh E2b-1              # một kịch bản không có khối chỉnh: R-F không ra line (phát hiện)
fpga/exp2b/run_exp2b.sh summary            # dòng kết quả của mọi run
fpga/exp2b/run_exp2b.sh recheck            # kiểm lại mọi output bằng công cụ hiện tại, không mô phỏng (~30 s)
fpga/exp2b/run_exp2b.sh evidence           # kiểm chứng toàn bộ output (§9)
fpga/exp2b/run_exp2b.sh evselftest         # thử chính script kiểm chứng trên các lỗi cài sẵn (§9)
python3 fpga/exp2b/tn2b_evidence.py report      # số đo theo rate (độ trễ, trailer, khởi động TX, bộ nhớ)
```

Bộ đầy đủ là `shim` và `finding`: 40 run, 4 build. Lần chạy 2026-10-26 dùng 3 luồng và xong trong 34 phút.

**Khối chỉnh:**

```bash
fpga/rtl/run_rtl.sh lint                   # VCS, 1, 2 và 4 lane: 0 error, warning, lint
fpga/rtl/run_rtl.sh rules                  # kiểm luật viết RTL
fpga/rtl/run_rtl.sh sim                    # unit testbench VCS, 1, 2 và 4 lane: TB RESULT: PASS
fpga/rtl/run_rtl.sh synth                  # Vivado out-of-context trên part của board (~2 phút)
fpga/rtl/run_rtl.sh all                    # cả bốn, theo thứ tự trên
```

## 9. Đọc kết quả

### 9.1 TN2a

**File của mỗi kịch bản** (`fpga/work/exp2/<tên>/`):

| File | Nội dung |
|---|---|
| `truth.txt` | Byte giải từ pad, theo lane và burst, kèm t0 và t1 (`pad_truth`) |
| `truth_gen.txt` | Truth của line generator, chỉ khi `+SRC=gen` |
| `expected.txt` | Byte đã giao cho TX, theo lane và burst |
| `xil_ppi.csv`, `ftel_ppi.csv` | PPI của RX AMD và của RX mình, định dạng ILA |
| `check.txt` | Kết quả so của `csi2_dump.py bursts` |
| `tbcheck.txt` | Kết quả `tn2a_evidence.py tbcheck` |
| `tb.txt` | Các dòng testbench in ra |
| `xsim.log` | Log của XSIM |
| `args.txt` | Tham số của lần chạy, mã băm nguồn của build, giới hạn trailer |

**`check.txt` của E2a-1:**

```
A xil_ppi.csv: 4 lane(s), 40/40 bursts carry the payload sent, trailer bytes 18..18 (in 40 bursts), latency of the last payload byte 27.5..27.5 ns, rxsynchs -1..-1 samples from the first byte, lane spread 0..0, errors 0
B ftel_ppi.csv: 4 lane(s), 40/40 bursts carry the payload sent, trailer bytes 0..0 (in 0 bursts), latency of the last payload byte 203.1..203.1 ns, rxsynchs +0..+0 samples from the first byte, lane spread 0..0, errors 0
RESULT: PASS (A 0 errors, B 0 errors)
```

Các trường đọc như ở TN1 ([`TN1_DESCRIPTION.md`](../exp1/TN1_DESCRIPTION.md) §9). Dòng `A` là RX AMD, dòng `B` là RX
mình.

**`tbcheck.txt` của E2a-1:**

```
TBCHECK done     ok   TB DONE      OK: NL 4, rate 1440.92 Mb/s (UI 0.694 ns), 10 b
TBCHECK pads     ok   40/40 lane bursts decoded, 5532 bytes, mismatches 0, unexpected 0, missing 0, without sync 0, short 0, line-state differences 0
TBCHECK front    ok   0 differences in 32674 changes (not counted, up to 2.5 ps: 0 of 0 comparisons differ)
TBCHECK afe      ok   term_en late 0, missing 0; clock lane late 0; line-state errors 0
TBCHECK tx       ok   10 bursts done of 10, 0 lane bursts without HS
TBRESULT: PASS (5/5 items)
```

**`tb.txt`**, ngoài các dòng giống TN1 (`TB DONE`, `TB FRONT END CHECK`, `AFE`, `TB FTEL CFG`):
- `TB TX CFG`, `TB TX`: chu kỳ clock, khởi động TX, số burst đã xong;
- `TB PADS` (kèm `TB PADS MISMATCH` khi có byte khác): kết quả của `pad_truth`;
- `TB TXTIMING`: mỗi tham số timing của TX một dòng, min và max, kèm giới hạn D-PHY v1.1 ở rate đó;
- `TB FRONT END CHECK START`: các lần so trước 2,5 ps, không tính.

### 9.2 TN2b

**File của mỗi kịch bản** (`fpga/work/exp2b/<tên>/`):

| File | Nội dung |
|---|---|
| `frames.txt` | Frame generator đã đưa ra |
| `tx_axis.csv`, `xil_axis.csv`, `ftel_axis.csv` | Đầu vào của TX, `video_out` của R-X và của R-F |
| `tx_ppi.csv`, `xil_ppi.csv`, `ftel_ppi.csv` | PPI bên trong TX, PPI của R-X, PPI vào R-F |
| `check.txt` | Kết quả của các lệnh `csi2_dump.py` (§6.2) |
| `tbcheck.txt` | Kết quả `tn2b_evidence.py tbcheck` |
| `tb.txt` | Các dòng testbench in ra |
| `xsim.log`, `args.txt`, `rss.txt` | Log của XSIM; tham số và mã băm nguồn; bộ nhớ của mô phỏng mỗi 10 s |

**`check.txt` của SH_E2b-1**, rút gọn: mỗi mục có một dòng `==` ghi lệnh, vài dòng kết quả, và một dòng `ITEM`.

```
== ppi-ftel: csi2_dump.py ppi ftel_ppi.csv --lanes
bursts 35 (partial 0), packets {'FS': 2, 'RAW10': 32, 'FE': 1}
ECC corrected 0, errors 0, CRC ok 32, trailer bytes max 0
image lines: WC [800] -> [640] pixels
timing: rxsynchs +0..+0 samples from the first byte (expected +0), lane spread 0..0 (at most 6), errors 0
ITEM ppi-ftel PASS
== packets-xil-ftel: compare ppi xil_ppi.csv ftel_ppi.csv
35 packets identical (A has 35, B has 35)
ITEM packets-xil-ftel PASS
RESULT: PASS (7 items)
```

**`tbcheck.txt` của SH_E2b-9**, dòng `regs` rút gọn:

```
TBCHECK done     ok   TB DONE OK
TBCHECK axil     ok   errors TX 0, R-X 0, R-F 0
TBCHECK tx       ok   core ready reached, 3/3 frames, 48/48 lines, ISR 0x00000000
TBCHECK regs     ok   shown, not judged: R-X ISR 0x80020000 frame received: (stop state); R-F ISR 0x80020201 frame received: VC0-3 frame sync/level, CRC, (stop state); unknown bits 0x0f000000; packet count R-X 48 R-F 47
TBCHECK axis     ok   tx 48 lines 3 frames, xil 48 lines 3 frames, ftel 47 lines 3 frames; ftel shown, not judged
TBCHECK front    ok   0 differences in 224965 changes (not counted, up to 2.5 ps: 0 of 0 comparisons differ)
TBCHECK afe      ok   term_en late 0, missing 0; clock lane late 0
TBCHECK adapter  ok   the gate against the model of the testbench: 20802 comparisons, 0 differences
TBCHECK sotsync  ok   lane 0 packet 5: 1 bursts given the SoT sync error
TBRESULT: PASS (9/9 items)
```

- "shown, not judged": mục đó chỉ báo cáo ở kịch bản này (§6.2, ngoại lệ).
- "unknown bits": bit đọc ra X trong thanh ghi ([`TN2_REPORT.md`](TN2_REPORT.md) §4.4).

**`tb.txt`**, ngoài các dòng giống TN1:
- `TB REG <subsystem> <offset> <giá trị>`: thanh ghi của ba subsystem ở cuối run;
- `TB AXIS`: số beat, line và frame của ba luồng;
- `TB TX`: khởi động TX, lúc controller xin HS clock, lúc mỗi RX thấy HS;
- `TB RX CFG`: lúc mỗi RX được cấu hình;
- `TB ADAPTER`, `TB ADAPTER CHECK`: khối chỉnh có được dùng không, và kết quả so với model;
- `TB CORRUPT`, `TB SOTSYNCERR`, `TB DIAG`: các can thiệp trên PPI vào R-F;
- `TB AXIL`: mỗi truy cập AXI4-Lite.

### 9.3 Tổng hợp và kiểm chứng

- `run_exp2.sh summary` và `run_exp2b.sh summary` in một dòng cho mỗi run, gồm kết luận của `check.txt` và của
  `tbcheck.txt`, ví dụ `SH_E2b-1       RESULT: PASS (7 items) | TBRESULT: PASS (8/8 items)`.
- `tn2a_evidence.py evidence` kiểm lại toàn bộ output TN2a bằng code riêng (10 check) và in
  `EVIDENCE: PASS (10/10 checks)` khi mọi check đạt. `tn2b_evidence.py evidence` làm như vậy cho TN2b (12 check). Mỗi
  check cần đủ bộ run ở §8.
- `evselftest` thử chính script kiểm chứng: cài lần lượt từng lỗi vào bản copy của output thật, và đòi mỗi lỗi làm
  hỏng đúng check của nó, không thừa, không thiếu; khi không cài lỗi thì mọi check phải đạt. TN2a có 12 lỗi, TN2b có
  19 lỗi. Trong đó có ba lỗi giống các lỗi tester team FPGA đã cài vào capture của TN1. Danh sách đầy đủ nằm trong
  `EV_FAULTS` của mỗi script. Output thật không bị đụng.
- `recheck` chạy lại phần so cho mọi output mà không mô phỏng lại. Lệnh này ghi đè `check.txt` và `tbcheck.txt`.

Kết quả mong đợi và cách hiểu các con số nằm ở [`TN2_REPORT.md`](TN2_REPORT.md).

## 10. Chạy kịch bản riêng

```bash
fpga/exp2/run_exp2.sh run 1440 4 my_test +PATTERN=prbs9 +LENS=1,8,64        # TN2a, cả hai RX
MAXTR=4 fpga/exp2/run_exp2.sh run 260 4 my_260 +TIMEOUT_US=3000            # cho RX mình tối đa 4 byte trailer
fpga/exp2b/run_exp2b.sh run 1440 my_frames +PATTERN=prbs +FRAMES=4         # TN2b, không có khối chỉnh
EXP2B_ARGS=+PPI_ADAPTER=1 fpga/exp2b/run_exp2b.sh run 1440 my_gate +FRAMES=4   # TN2b, qua khối chỉnh
```

- Rate hoặc số lane mới thì script tự build trước.
- TN2a: `MAXTR` đặt số byte trailer tối đa cho RX mình, mặc định 0. `+SRC=gen` dùng được mọi plusarg timing của line
  generator TN1.
- TN2b: `EXP2B_ARGS` thêm plusarg vào mọi run, `EXP2B_TAG` thêm tiền tố vào tên run. Lệnh `shim` đặt hai biến này thành
  `+PPI_ADAPTER=1` và `SH_`.
- `+HS_SETTLE=`, `+CLK_SETTLE=`, `+EOT_SKIP=`, `+TINIT=` ghi đè cấu hình theo rate của RX mình, như TN1.
- `EXP2_DEBUG=typical`, `EXP2B_DEBUG=typical` giữ tín hiệu để xem waveform, kèm `+VCD=1`. Hai biến này cần build mới.
- Danh sách đủ plusarg nằm ở đầu [`tb_exp2a.sv`](tb_exp2a.sv) và [`tb_exp2b.sv`](../exp2b/tb_exp2b.sv).

## 11. Bench không kiểm những gì

- **Phần cứng:** TX, RX AMD, ba subsystem và `IBUFDS_DPHY` đều là model mô phỏng của AMD. RTL của các controller
  CSI-2 đã mã hoá, nên hành vi của chúng chỉ biết qua thử.
- **Analog:** pad chỉ là mức logic; không có jitter, ISI, skew giữa lane. TN1 đã phủ skew tới 7,5 byte time.
- **Góc timing của TX:** IP không cho chỉnh, nên mỗi rate chỉ có một điểm timing. TN1 đã phủ các góc bằng line
  generator.
- **Lệch clock ở phía TX:** model clock của TX không cho lệch; thay bằng lệch `core_clk` ở phía RX.
- **Metastability và CDC:** RTL chạy zero-delay. Phần này thuộc phân tích CDC của build FPGA.
- **Chưa chạy:** ULPS, escape mode, deskew, non-continuous clock, nhiều virtual channel, data type khác RAW10, embedded
  data, frame camera thật, và 400, 600, 1000, 1200 Mb/s ở mức CSI-2 (mức PHY ở các rate này có trong TN2a).
- **Lỗi SoT sync ở phía D-PHY AMD:** E2b-9 chỉ cài lỗi trên PPI vào R-F; bench không có cách cài lỗi sync vào line của
  TX AMD.
- **`stopstate`:** có ghi trong CSV nhưng không so.

## 12. Lưu ý cho prototype FPGA (TN3)

- **Khối chỉnh `rxactivehs` phải có trong R-F**, giữa `ftel_dphy_rx` và CSI-2 RX Subsystem không PHY, nối như §5.3.
  Không có nó, controller của AMD không nhận packet nào ([`TN2_REPORT.md`](TN2_REPORT.md) §4.1).
- **Thứ tự cấu hình:** theo thứ tự của AMD, tức cấu hình RX trước khi TX chạy, là được. Khi R-F được cấu hình lúc
  `ftel_dphy_rx` chưa có byte clock, bit 27:24 trong ISR của R-F đọc ra X trong mô phỏng. Driver của AMD che các bit này
  bằng mặt nạ ngắt 0xF07FFFFF. Nếu muốn các bit đó sạch, cấu hình (hoặc soft reset) R-F sau khi clock lane vào HS
  ([`TN2_REPORT.md`](TN2_REPORT.md) §4.4).
- **`video_out` không đánh dấu line hỏng:** với dữ liệu pixel, `tuser[1]` luôn bằng 0. ILA trên `video_out` vì vậy
  không tự thấy line hỏng; cần đọc ISR, hoặc bắt cả PPI ([`TN2_REPORT.md`](TN2_REPORT.md) §4.7).
- **Đọc RTL `ftel_dphy_rx` bằng Vivado:** RTL khai báo port `input logic` dưới `` `default_nettype none ``. XSIM nhận
  kiểu này khi có `--relax`, và các script của bench đặt `--relax` cho cả compile lẫn elaborate. Khối chỉnh đã gặp lỗi
  VRFC 10-1103 với kiểu port này khi synth bằng Vivado, nên đã khai báo `input var logic`. RTL của `ftel_dphy_rx` mới
  được synth bằng Design Compiler, chưa được synth bằng Vivado. Cách xử lý trong flow FPGA chưa chốt; RTL ASIC không
  sửa chỉ để hợp với tool.
- **Phần riêng cho ASIC** của `ftel_dphy_rx` (khối AFE adapter, lấy mẫu bằng clock DDR của clock lane) như ở
  [`TN1_DESCRIPTION.md`](../exp1/TN1_DESCRIPTION.md) §12.
