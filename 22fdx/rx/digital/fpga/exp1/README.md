# TN1: so sánh RX D-PHY `ftel_dphy_rx` với RX D-PHY của AMD (Xilinx), mô phỏng XSIM

Thí nghiệm TN1 của [`../PLAN_TN1_TN3.md`](../PLAN_TN1_TN3.md) §1.
- Các lỗi TN1 tìm ra được sửa theo [`../PLAN_TN1_FIX.md`](../PLAN_TN1_FIX.md).
- Từ 2026-10-20, hai RX đứng sau cùng một front end, để so công bằng phần digital
  ([`../PLAN_TN1_FAIR.md`](../PLAN_TN1_FAIR.md)).

Kết quả ở §6 là của lần chạy 2026-10-20 với bench theo `PLAN_TN1_FAIR.md`, trên RTL tại commit `465ff69` (HAS v0.16).

README này là ghi chép kỹ thuật của nhóm. Cho team FPGA có hai tài liệu riêng, không dùng thuật ngữ nội bộ:
[`TN1_DESCRIPTION.md`](TN1_DESCRIPTION.md) (mô tả thí nghiệm, cách chạy) và [`TN1_REPORT.md`](TN1_REPORT.md) (báo
cáo kết quả).

## 1. Mục đích

TN1 trả lời ba câu hỏi:
1. Cùng một tín hiệu D-PHY trên pad, RX mình và RX AMD có ra cùng dữ liệu ở PPI không?
2. Cả hai có nhận đúng các byte đã phát không?
3. Khi hai RX đứng sau cùng một front end và chịu cùng bộ kịch bản, phần digital của RX mình có làm được như phần
   digital của AMD không?

Ngoài ra đây là lần đầu RTL `ftel_dphy_rx` chạy trọn từ pad tới PPI. RX AMD là IP đã dùng thực tế, nên nó
đóng vai mốc tham chiếu. Nếu RX AMD đạt thì line generator đúng, và lỗi nào chỉ xuất hiện ở RX mình là lỗi
của RX mình.

## 2. Sơ đồ

```
dphy_line_gen (Tx giả, D-PHY v1.1, mức logic trên pad) ──► truth.txt (byte đã phát, theo lane/burst)
   │ clk_p/n, d_p/n[0..3]
   ├─► RX AMD, mipi_dphy 4.3 SLAVE: assign → IBUFDS_DPHY → XPHY → controller ───► PPI ─► xil_ppi.csv  ─┐
   ├─► IBUFDS_DPHY (cùng model, cùng SIM_DEVICE) ─┐ +AFE=xil (mặc định)                                │
   │                                              ├─► m_ftel_dphy_rx_wrap (RTL ASIC) ─► PPI ─► ftel_ppi.csv ─┤
   └─► afe_model (AFE lý tưởng) ──────────────────┘ +AFE=model                                          │
         luôn chạy: kiểm trạng thái line và term_en       csi2_dump.py bursts: mỗi CSV so với truth.txt ┘

Check trong bench: đầu ra LP của các buffer AMD và của các buffer trước RX mình phải trùng nhau ở mọi lần đổi.
```

Mô phỏng chạy trong XSIM của Vivado 2025.2, part xcvp1902.

## 3. Các khối

**Line generator** ([`dphy_line_gen.sv`](dphy_line_gen.sv)):
- **Clock lane:** đi LP-11 → LP-01 → LP-00 → HS-0 một lần, rồi chạy continuous. Cạnh clock nằm giữa bit.
- **Mỗi burst, mọi lane cùng lúc:** LP-11 → LP-01 (TLPX) → LP-00 (THS-PREPARE) → HS-0 (THS-ZERO) → sync 0xB8
  → payload (LSB trước) → trail (đảo của bit cuối, THS-TRAIL) → LP-11. Sau đó chờ THS-EXIT rồi mới phát burst
  kế.
- **Mức trên pad:** pad chỉ là mức logic, không có analog. HS là Dp = bit, Dn = ~bit. Skew của từng lane là
  transport delay.
- **Timing mặc định** nằm giữa khoảng D-PHY v1.1 ([`tb_exp1.sv`](tb_exp1.sv), `p_main`). Ví dụ ở 1440 Mb/s:
  - TLPX 75 ns;
  - THS-PREPARE 66 ns;
  - PREPARE + ZERO bằng 1,2 lần mức min (182 ns so với 152 ns);
  - THS-TRAIL bằng 1,2 lần mức min (75 ns);
  - THS-EXIT 150 ns.
- **File truth:** ghi từng lane, từng burst: số byte, thời điểm bit sync đầu tiên, thời điểm kết thúc payload,
  và payload.

**Front end của RX mình** (`+AFE=xil|model`, [`tb_exp1.sv`](tb_exp1.sv)):
- **`IBUFDS_DPHY`, mặc định.**
  - Đây là primitive mà IP AMD đặt ở mỗi cặp pin, dùng cùng `SIM_DEVICE "VERSAL_PREMIUM"`. Có một buffer cho mỗi
    data lane và một cho clock lane.
  - LP receiver luôn bật, như trong IP AMD. HS receiver bật theo `hs_en` của RTL mình; bên AMD, controller của
    AMD tự bật.
  - Model của AMD làm như sau:
    - LP output đi theo pad khi cả hai pin được lái với strength "S" (strong hoặc supply), còn lại bằng 00;
    - HS output đi theo Dp/Dn, giữ giá trị cũ khi Dp = Dn, và bằng 0 khi HS receiver tắt.
  - **Pad vào cả hai buffer đều là strong.** IP AMD đưa pad qua một `assign` thường (`xrx_core.v` của IP sinh ra),
    và trong testbench pad là biến. Hệ quả cho cả hai RX:
    - trong HS, LP output đổi theo data, trong khi trên silicon thì đọc LP-00;
    - sau LP-11, HS output giữ bit cuối.
- **`afe_model`** ([`afe_model.sv`](afe_model.sv)), với `+AFE=model`:
  - Suy ra trạng thái line từ chuỗi LP trên pad. Trong HS, LP receiver đọc LP-00, giống silicon.
  - HS output bằng Dp khi đang HS và `hs_en` bật, ngoài ra bằng 0. Mô hình không có trễ.
  - Luôn chạy, ở cả hai chế độ, để kiểm phụ:
    - `term_en` có bật kịp trong TD-TERM-EN không;
    - trạng thái line suy ra có khớp generator không.

    Ở lần chạy 2026-10-20: 0 lỗi trong cả 227 run.

**RX AMD** ([`exp1.tcl`](exp1.tcl)):
- IP `mipi_dphy` 4.3, SLAVE, SupportLevel 1, C_INIT 99 µs; các tham số khác để mặc định của IP theo rate.
- Line rate cố định lúc build, nên mỗi tổ hợp rate × số lane là một build riêng.
- Trên xcvp1902, IP này chỉ chạy 260–3200 Mb/s.

**RX mình:**
- RTL lấy nguyên từ [`logical/filelist.f`](../../logical/filelist.f).
- Field run-time (`hs_settle_cyc`, `clk_settle_cyc`, `eot_skip_bytes`) lấy từ model của
  [`validate_config.py`](../../config/validate_config.py) theo rate
  ([`cfg_for_rate.py`](cfg_for_rate.py)). `tinit` là 100 µs.

**Monitor** ([`ppi_csv_mon.sv`](ppi_csv_mon.sv)):
- Mỗi RX ghi một file CSV đúng format ILA của Vivado.
- Mẫu được lấy ở cạnh lên `rxbyteclkhs` của chính RX đó.
- Cột: `rxdatahs`, `rxvalidhs`, `rxactivehs`, `rxsynchs`, `errsoths`, `errsotsynchs`, `stopstate`, `cl_stopstate`.
- Cùng công cụ này sẽ đọc capture ILA thật ở TN3.

**Trình tự một lần chạy:**
1. Nhả reset.
2. Chờ cả hai RX báo `init_done` (khoảng 100 µs, line đứng ở LP-11).
3. Clock lane vào HS.
4. Phát lần lượt các burst.
5. Chờ delay line xả hết rồi kết thúc.

## 4. Điều kiện so sánh

**Cách so:**
- Hai RX nhận đúng cùng một waveform, cùng lúc, cùng `core_clk` 200 MHz.
- Cả hai đứng sau cùng một front end: cùng `IBUFDS_DPHY`, cùng strength trên pad. Bench kiểm điều này ở mọi run.
- Cả hai chạy cùng bộ kịch bản, kể cả stress EoT E1-5.
- Hai RX không so trực tiếp từng chu kỳ với nhau, vì mỗi RX có byte clock và độ trễ riêng. Thay vào đó, mỗi file
  CSV được so với cùng một file truth theo cùng một bộ luật ([`../tools/csi2_dump.py`](../tools/csi2_dump.py), mode
  `bursts`).

**Một burst trên một lane đạt khi đủ cả các điều kiện sau:**

| Điều kiện | Cách kiểm |
|---|---|
| Burst định nghĩa thế nào | Mỗi lần `rxactivehs` = 1 liên tục là một burst. Byte của burst là các mẫu có `rxvalidhs` = 1 |
| Ghép với truth | Burst thứ k trong capture của một lane ghép với burst thứ k của lane đó trong truth (theo thứ tự, không theo nội dung) |
| Số burst | Mỗi lane đủ đúng số burst của truth: không thiếu, không thừa, không burst nào còn mở lúc kết thúc |
| Payload | N byte đầu của burst thứ k phải bằng đúng payload của burst k trong truth, đúng thứ tự |
| Ghép đúng cả về thời gian | Byte cuối của burst (trong N byte đầu) phải tới PPI sau khi nó rời pad, và trễ xấp xỉ trung vị của capture: lệch không quá nửa khoảng cách nhỏ nhất giữa hai burst của một lane. Luật này cần vì payload có thể lặp lại: nếu một lane mất một burst rồi thừa một burst khác, số burst và payload vẫn có thể khớp theo thứ tự, chỉ có thời gian lộ ra |
| Cờ trong burst | `rxsynchs` lên đúng 1 lần; `errsoths` và `errsotsynchs` không lên |
| Ngoài burst | Không có `rxvalidhs` hay cờ nào, không có giá trị X |
| Byte trailer (sau payload) | RX AMD: không giới hạn, vì IP này không cắt trailer. RX mình: tối đa theo HAS Table 4-7 (0 nếu không nhiễu, từ 600 Mb/s) |

Kịch bản chỉ PASS khi cả hai RX đều 0 lỗi.

**Vẫn khác sau khi đã cùng front end** (do thiết kế; mỗi bên so trọn đường digital của mình, tính từ đầu ra buffer):
- **Deserializer:** AMD dùng XPHY (khối cứng), mình dùng Block No. 1 (RTL). Muốn giống hệt tới tận deserializer thì
  phải làm TN2c.
- **Bật HS receiver:** mỗi RX tự bật bằng logic của mình. Đây là một phần của phần digital được so.
- **Cấu hình:** AMD để mặc định của IP theo rate; RX mình dùng giá trị model HAS.
- **Trailer:** RX AMD theo thiết kế giữ trailer; RX mình cắt.

**Khác biệt chỉ ghi nhận, không tính lỗi:**
- số byte trailer của RX AMD;
- độ trễ của byte payload cuối;
- thời điểm `stopstate`: có ghi trong CSV nhưng không kiểm, vì đó là mục ADR-006.

## 5. Các test

| ID | Rate (Mb/s), lane | Nội dung | Mục đích | RX |
|---|---|---|---|---|
| E1-1 | 1440, 4 | Burst 1–1024 byte, payload counter | Cơ bản, ở rate của camera | Cả hai |
| E1-2a | 1440, 4 | Payload PRBS-9, mỗi độ dài 2 lần | Dữ liệu ngẫu nhiên | Cả hai |
| E1-2b | 1440, 4 | Payload chứa 0xB8 và 0xB8 dịch 1–7 bit qua ranh giới byte | Sync chỉ khoá một lần, không khoá nhầm trong payload | Cả hai |
| E1-2c | 1440, 4 | Lane 2–3 ít hơn 1 byte | Lane kết thúc lệch nhau, như packet có độ dài không chia hết 4 | Cả hai |
| E1-3a/b | 1440, 4 | THS-PREPARE min/max, PREPARE + ZERO ở mức min | Biên đầu burst | Cả hai |
| E1-3c | 1440, 4 | THS-TRAIL, THS-EXIT, TLPX đều min | Biên cuối burst, burst sát nhau | Cả hai |
| E1-3d/e/f | 1440, 4 | Clock lệch 139 ps (0,2 UI); mọi data lane lệch 139 ps; lane lệch nhau 0/46/93/139 ps | Skew | Cả hai |
| E1-3g | 1440, 4 | `afe_model` ra bit ngẫu nhiên trong LP-00 | Nhiễu trước HS. Nhiễu là của `afe_model`, nên RX mình đứng sau `afe_model`; đây là test riêng của RX mình | Cả hai chạy; chỉ RX mình chịu nhiễu |
| E1-4a | 260, 4 | Timing mặc định và timing min | Rate thấp nhất mà IP AMD chạy được | Cả hai |
| E1-4b/c | 800 / 1500, 4 | Rate | Phủ dải R1 | Cả hai |
| E1-4d/e | 1440, 2 / 1 | Số lane | 1, 2 lane | Cả hai |
| E1-5 (96 run) | 260–1500, 4 | 8 rate × trail min/mặc định/max × có/không jitter trail (0–7 bit) × nhiễu 0/40 ns trước LP-11; `core_clk` lệch 400 ppm | Stress EoT | Cả hai |
| `M_*` (113 run) | như trên | Đúng các kịch bản trên, RX mình đứng sau `afe_model` (LP-00 trong HS như silicon) | Bộ phụ: RX mình với front end giống AFE thật hơn | Cả hai |
| R-80 | 80, 4 | Ngoài phạm vi bảo đảm | Chỉ báo cáo, không tính PASS/FAIL | Chỉ RX mình (stub) |

**E1-5 chạy cả hai RX.**
- Cần 8 build, một build cho mỗi rate.
- Giới hạn trailer chỉ áp cho RX mình, vì RX AMD theo thiết kế không cắt trailer.
- Ở chế độ `stub`, chỗ của IP AMD được thay bằng một khối rỗng ([`xrx_stub.sv`](xrx_stub.sv)). Chế độ này chỉ còn
  dùng cho R-80 (rate mà IP AMD không build được) và cho `window`.

Ngoài các test trên còn có `run_exp1.sh window`. Đây là phép đo, không phải test đạt/hỏng:
- nó quét `eot_skip_bytes` quanh giá trị model ([`eot_window.py`](eot_window.py) in bảng), và cho ra các con số
  của HAS Table 4-7;
- nó chạy với `+AFE=model`, như lúc đo Table 4-7. HS output về 0 từ LP-11 là trường hợp xấu hơn (§6).

## 6. Kết quả lần chạy 2026-10-20

**Chế độ công bằng: 113/113 kịch bản PASS cho cả hai RX. Bộ phụ `M_*`: 113/113 PASS. R-80: payload nguyên
36/36 burst, dư 0–1 byte trailer ở 10 burst.**

Lần chạy đầu, RX mình hỏng hai lỗi: mất byte cuối burst, và có `rxvalidhs` nằm ngoài `rxactivehs`. Cả hai đã
sửa theo `PLAN_TN1_FIX.md` (HAS v0.16).

**E1-1…E1-4** (byte trailer mỗi burst; độ trễ byte payload cuối):

| Rate (Mb/s) | Kịch bản | Trailer: AMD | Trailer: RX mình sau `IBUFDS_DPHY` | Trailer: RX mình sau `afe_model` | Độ trễ: AMD | Độ trễ: RX mình |
|---|---|---|---|---|---|---|
| 260 | E1-4a / E1-4a timing min | 2 / 1–2 | 0 / 0 | 0 / 0–2 (8 trong 40 burst) | 152–179 ns | 1113–1140 ns |
| 800 | E1-4b | 9 | 0 | 0 | 50–58 ns | 362–371 ns |
| 1440 | E1-1…E1-3, E1-4d/e | 14–17 | 0 | 0 | 27–32 ns | 201–206 ns |
| 1500 | E1-4c | 17–18 | 0 | 0 | 26–31 ns | 193–198 ns |

**E1-5** (stress EoT, 432 burst-lane mỗi ô):
- Ở mọi ô, cả hai RX đều nhận đủ 432/432 payload.
- Trailer ghi dạng "khoảng (số burst có trailer)".
- Ô "giống bên trái" nghĩa là trùng cả khoảng lẫn số burst.

| Rate (Mb/s) | Nhiễu | Trailer: AMD | Trailer: RX mình sau `IBUFDS_DPHY` | Trailer: RX mình sau `afe_model` | Giới hạn (Table 4-7) |
|---|---|---|---|---|---|
| 260 | không | 1–4 | 0 | 0–4 (67) | 4 |
| 260 | 40 ns | 1–4 | 0–4 (429) | giống bên trái | 4 |
| 400 | không | 3–7 | 0 | 0–4 (4) | 6 |
| 400 | 40 ns | 2–7 | 0–5 (426) | giống bên trái | 6 |
| 600 | không | 5–10 | 0 | 0 | 0 |
| 600 | 40 ns | 5–10 | 0–7 (421) | giống bên trái | 7 |
| 800 | không | 7–13 | 0 | 0 | 0 |
| 800 | 40 ns | 6–13 | 0–8 (328) | giống bên trái | 8 |
| 1000 | không | 9–17 | 0 | 0 | 0 |
| 1000 | 40 ns | 8–16 | 0–8 (15) | giống bên trái | 9 |
| 1200 | không / 40 ns | 11–20 | 0 | 0 | 0 / 10 |
| 1440 | không | 14–24 | 0 | 0 | 0 |
| 1440 | 40 ns | 13–24 | 0–12 (4) | giống bên trái | 12 |
| 1500 | không / 40 ns | 14–25 | 0 | 0 | 0 / 12 |

**Đọc kết quả:**
- **Payload:** cùng front end và cùng kịch bản, phần digital của RX mình nhận đúng mọi payload như phần digital
  của AMD, ở cả 8 rate.
- **Trailer:**
  - RX mình cắt trailer, RX AMD giữ (tới 25 byte ở 1500 Mb/s).
  - Sau `IBUFDS_DPHY`, RX mình còn ít hoặc bằng trailer so với khi đứng sau `afe_model`. Lý do: model AMD giữ bit
    trail sau LP-11, còn `afe_model` ép về 0. Table 4-7, đo sau `afe_model`, vẫn là trường hợp xấu hơn.
- **Độ trễ:** RX mình trễ hơn khoảng 6–7 lần, vì delay line 32 byte cần cho phép cắt trailer. Độ trễ không phụ
  thuộc front end.

Chi tiết từng kịch bản nằm trong `fpga/work/exp1/<tên>/check.txt` (gitignored) và ở
[`doc/rtl_notes.md`](../../doc/rtl_notes.md) §9.

## 7. Kiểm chứng: vì sao tin được kết quả

Kết quả chỉ đáng tin khi trả lời được sáu câu hỏi dưới đây, mỗi lớp kiểm một câu.
[`tn1_evidence.py`](tn1_evidence.py) kiểm lại tự động từ output trong `fpga/work/exp1`:
- các lớp 1, 3, 4 và 6;
- selftest của bộ kiểm ở lớp 2 (`checker`);
- phép đo biên ở lớp 5 (`margin`).

```bash
python3 fpga/exp1/tn1_evidence.py          # mỗi check một dòng PASS/FAIL, rồi EVIDENCE: PASS/FAIL
```

Kết quả ngày 2026-10-20: **EVIDENCE: PASS (8/8 checks)**.

| Check | Kiểm gì | Kết quả 2026-10-20 |
|---|---|---|
| `checker` | Selftest của `csi2_dump.py`: tìm được các lỗi cài sẵn, kể cả ca chỉ sai thời gian; capture sạch thì đạt | PASS |
| `decode` | Giải mã lại mọi capture bằng code riêng, theo thứ tự và theo thời gian; kết quả phải trùng `check.txt`. Bộ giải mã tự thử trên capture giả trước | 453/453 capture |
| `runs` | Mọi run kết thúc `TB DONE OK`; file truth có một dòng cho mỗi burst và lane | 227/227 run |
| `front` | Mỗi run có hai RX: đầu ra LP của buffer AMD và của buffer trước RX mình trùng nhau ở mọi lần đổi; RX mình đứng sau `IBUFDS_DPHY` trừ khi kịch bản đặt `+AFE=model` | 226/226 run, 4 854 302 lần đổi, 0 khác |
| `afe` | Mô hình AFE không lỗi trạng thái; `term_en` không trễ, không thiếu | 227/227 run |
| `config` | Cấu hình RX mình đúng giá trị model HAS cho rate đó, hoặc giá trị kịch bản đặt | 227/227 run |
| `sources` | Mã băm nguồn của mọi build bằng mã băm nguồn hiện tại | 11/11 build |
| `margin` | Trail min: `eot_skip_bytes` model + 1 không mất payload, model + 2 mất, ở mọi rate | 8/8 rate |

Các con số trong bảng:
- 227 run = 113 kịch bản ở chế độ công bằng + 113 kịch bản của bộ phụ `M_*` + R-80.
- 453 capture = 226 run có hai RX × 2 + 1 capture của R-80.

### 7.1 Lớp 1: tín hiệu phát vào có đúng không?

- **RX AMD là mốc độc lập.** IP này do AMD viết. Nó nhận đúng mọi burst trong cả 226 run có nó, 0 lỗi. Nếu
  generator sai thứ tự bit, sai mẫu sync, sai pha clock, hay đặt timing ngoài chuẩn, RX AMD đã báo lỗi. Đây chính
  là điều kiện tiên quyết của plan.
- **Timing được in ra ở mỗi run** (dòng `TB LINE` trong `tb.txt`) và tính từ công thức D-PHY v1.1. Các góc đặt
  đúng biên. Ví dụ ở E1-3a/b, PREPARE + ZERO bằng đúng mức min 151,94 ns tại 1440 Mb/s.
- **Trạng thái line được kiểm độc lập.** Trạng thái mà `afe_model` suy ra được so với trạng thái generator thật sự
  phát, ở mọi lần đổi (check `afe`).

### 7.2 Lớp 2: bộ kiểm có biết báo FAIL không?

| Bằng chứng | Kết quả |
|---|---|
| Selftest của `csi2_dump.py`: capture giả có cài sẵn 4 lỗi (đảo một byte, mất một burst, `errsoths`, `rxsynchs` hai lần) | Bắt đủ 4 lỗi; capture sạch thì 0 lỗi |
| Selftest của `csi2_dump.py`: một lane có 8 burst cùng payload, mất burst 5 rồi phát lại burst 7. Số burst và payload vẫn khớp theo thứ tự | Luật thời gian bắt đúng 3 burst lệch, bắt đầu từ burst 5 |
| Lần chạy đầu (2026-10-19, RTL v0.15), cùng line, cùng bộ kiểm | AMD 40/40 burst đúng ở E1-1; RX mình chỉ 20/40 (E1-1), 0/16 (E1-3c), 0/40 (E1-4b). Nguyên nhân tìm được trong code RTL (F1, F2) |
| Cố tình đặt `eot_skip_bytes` model + 2 (`run_exp1.sh window`) | Báo mất payload ở mọi rate, ví dụ 711 / 2240 burst ở 260 Mb/s với trail min |
| Lần chạy thứ hai (RTL v0.16 bản đầu) | Bắt được 2 run E1-5 vượt Table 4-7 bản cũ, dẫn tới việc đo lại |

PASS chỉ xuất hiện sau khi sửa code, và các chỗ sửa đó giải thích được các lỗi đã thấy. Output của lần chạy đầu nằm
ở `fpga/work/exp1/_v015`, thư mục git bỏ qua, nên số liệu được ghi lại ở đây.

### 7.3 Lớp 3: PASS có được tính đúng không?

`tn1_evidence.py` giải mã lại mọi capture bằng code viết riêng, không dùng chung dòng nào với `csi2_dump.py`:
- burst là mỗi lần `rxactivehs` = 1 liên tục; byte là các mẫu có `rxvalidhs` = 1;
- so với `truth.txt` theo cùng luật ở §4, gồm cả luật thời gian;
- kết quả phải trùng `check.txt`: số burst có payload đúng, khoảng byte trailer, và kết luận đạt/hỏng.

Trước đó, bộ giải mã tự thử trên capture giả: capture sạch phải đạt, và capture "mất burst 5, phát lại burst 7" phải
lộ ra 3 burst lệch thời gian.

Ngày 2026-10-20: 453/453 capture trùng, và 128/128 capture của `window` (chạy `tn1_evidence.py fpga/work/exp1/window`).

**Ghép theo thứ tự có đúng không?** Payload có thể lặp lại: 128 run `window` (REPEAT=40) có payload trùng nhau trên
cùng một lane, vì mẫu `counter` quay vòng sau 16 burst. Luật thời gian (§4) loại trừ việc ghép nhầm:
- Mọi run TN1 và mọi run `window` đạt đều ghép đúng cả về thời gian. Dải độ trễ rộng nhất chỉ bằng 7 % khoảng cách
  nhỏ nhất giữa hai burst (R-80), nên ghép lệch một burst sẽ lộ ngay.
- Hai capture `window` ở model + 2 (`W_1000_min_n40_s11`, `W_260_min_n40_s3`) có lane 1 mất trọn một burst. Từ burst
  140 (và 252) trở đi, các cặp lệch một vị trí. Luật thời gian chỉ đúng chỗ đó. Hai run này vốn đã FAIL vì sai số
  burst và mất payload.

Luật thời gian được thêm ngày 2026-10-20, sau các lần chạy. `run_exp1.sh recheck` đã kiểm lại toàn bộ output (không
mô phỏng lại): 355 run không đổi kết luận, bảng `window` (Table 4-7) giống hệt.

### 7.4 Lớp 4: thứ được test có đúng là thứ đã commit không?

- **Nguồn đã chạy trùng với repo.**
  - Mã băm nguồn của mọi build (RTL theo `filelist.f`, và `exp1/*.sv`) bằng mã băm nguồn hiện tại.
  - RTL không đổi kể từ commit `465ff69`.
  - Mọi build tự compile lại khi một file nguồn đổi.
- **Cấu hình mỗi run đúng giá trị model HAS cho rate đó.** Ví dụ E1-4b (800 Mb/s) chạy `eot_skip_bytes` 6; E1-1
  (1440 Mb/s) chạy 13. Không có giá trị nào được chỉnh tay cho qua.
- **Không run nào dừng giữa chừng.** Mọi run kết thúc `TB DONE OK`, và file truth có đủ burst × lane.

### 7.5 Lớp 5: kết quả EoT có phải do may không?

- **Lần đo đầu đã "may" thật.** `core_clk` chạy đúng tỉ lệ cố định với đường truyền, nên chỉ gặp vài pha. Lỗi
  này lộ ra vì E1-5 dùng seed khác và hỏng.
- **Cách sửa:** cho `core_clk` lệch 400 ppm (`+CORE_HALF=2.501`), thêm jitter trail 0–7 bit, và chạy 1120 burst
  mỗi ô.
- **Biên được đo, không phải giả định:** với trail min, giá trị + 1 không bao giờ mất payload, còn + 2 mất ở mọi
  rate (check `margin`).
- **Bảng Table 4-7 khớp số đo.** Công thức số byte trailer tối đa của HAS Table 4-7 khớp hoặc chặn trên mọi số đo,
  ở cả hai front end (§6).

### 7.6 Lớp 6: hai RX có thật cùng front end không?

- **Từ mã nguồn IP AMD:**
  - IP AMD đặt `IBUFDS_DPHY` ở mỗi cặp pin, với `SIM_DEVICE "VERSAL_PREMIUM"`.
  - LP receiver luôn bật (`lp_rx_disable_w` = 0 trong `xrx_support.v`).
  - Pad đi qua `assign` thường (`xrx_core.v`, dòng 447–459), nên buffer luôn thấy strength strong.

  Bench đặt trước RX mình đúng primitive đó, cùng `SIM_DEVICE`, cùng strength, LP receiver cũng luôn bật.
- **Kiểm ở mọi run** (check `front`): bench so đầu ra LP của hai bộ buffer 2 ps sau mỗi lần đổi. Kết quả: 226/226
  run có hai RX, 4 854 302 lần so, 0 khác.
- **Check này biết báo FAIL.** Phép thử âm [`neg_front.sh`](neg_front.sh) chạy E1-1 trên một bản copy của build
  1440 Mb/s, và không sửa nguồn trong repo:
  - buffer của RX mình được lái pull trong HS, tức phương án đã bỏ ở `PLAN_TN1_FAIR.md` §8;
  - kết quả: 21 574 / 30 450 lần đổi khác nhau, `front` FAIL, script in `NEGATIVE TEST PASS`.
- **Bộ phụ khớp lần chạy trước.** Bộ `M_*` (RX mình sau `afe_model`) và 128 run `window` trên bench mới ra
  `truth.txt` và capture giống từng byte với lần chạy trước khi đổi bench: 500/500 file. Lần chạy đó được lưu ở
  `fpga/work/exp1/_v016_model` (chỉ có trên máy này). Vậy việc thêm front end không làm đổi kết quả cũ. Lệnh so:

  ```bash
  cd fpga/work/exp1 && for d in _v016_model/E1-* _v016_model/R-80 _v016_model/window/W_*; do
    n=${d#_v016_model/}; f="truth.txt ftel_ppi.csv"
    case $n in R-80) f=truth.txt ;; E1-5_*) n=M_$n ;; window/*) ;; *) n=M_$n; f="$f xil_ppi.csv" ;; esac
    for x in $f; do cmp -s "$d/$x" "$n/$x" && echo same || echo "differs: $n/$x"; done
  done | sort | uniq -c        # 2026-10-20: 500 same
  ```

  E1-5 cũ chạy stub, không có RX AMD, nên chỉ so capture của RX mình. R-80 nay đứng sau `IBUFDS_DPHY`, nên chỉ so
  `truth.txt`.

### 7.7 Kiểm chính `tn1_evidence.py`

Script kiểm chứng cũng phải biết báo FAIL. Các phép thử ngày 2026-10-20:
- **Đổi 1 bit payload** trong `ftel_ppi.csv` của một bản copy E1-1: check `decode` FAIL, vì giải mã lại thấy
  39/40 burst đúng trong khi `check.txt` ghi 40/40.
- **Chạy trên output lần chạy đầu (`_v015`):**
  - `decode` vẫn trùng 65/65, kể cả các capture hỏng;
  - `config` FAIL: các run đó dùng `eot_skip_bytes` 15 của model cũ, model nay cho 13;
  - `afe` FAIL ở 5 run 80 Mb/s có burst quá sát nhau, `term_en` bị thiếu;
  - `sources` FAIL: thư mục đó không có build.
- **Hai front end khác nhau** ([`neg_front.sh`](neg_front.sh), §7.6): `front` FAIL.
- **Gỡ luật thời gian khỏi bộ giải mã** (bản copy tạm): selftest của bộ giải mã FAIL, nên `decode` FAIL.

### 7.8 Giới hạn của phần kiểm chứng

1. `run_exp1.sh` chưa tự tính timeout là FAIL. `tn1_evidence.py` kiểm điều này (check `runs`).
2. **Front end chung là model mô phỏng của AMD, không phải AFE thật.**
   - Trong HS, model cho LP đổi theo data; silicon thì cho LP-00. Bộ phụ `M_*` phủ trường hợp LP-00, và RX mình
     đạt ở cả hai.
   - `afe_model` do mình viết và lý tưởng. Độ giống AFE thật: LOW, chỉ kiểm được bằng phần cứng (ADR-001).
3. RX AMD trong XSIM là mô hình mô phỏng của AMD, không phải phần cứng. TN3 trên board sẽ xác nhận.
4. RTL mô phỏng zero-delay, không có metastability. Phần đó thuộc phân tích CDC (M4) và STA, không thuộc TN1.
5. Chỉ kiểm theo kịch bản, không có số đo functional coverage.

**Độ tin cậy:**
- HIGH:
  - PASS là thật trong điều kiện đã mô phỏng;
  - hai RX cùng front end (đọc từ mã nguồn IP, kiểm ở mọi run, có phép thử âm).
- MED: số byte trailer tối đa, vì hằng số 29 ns là số khớp từ đo.
- LOW: chuyển kết luận sang silicon, vì cả hai front end đều là model.

## 8. TN1 không kiểm những gì

- **ULPS, escape mode, deskew, non-continuous clock.** Plan gốc có E1-5 (ULPS, tuỳ chọn) và E1-6
  (non-continuous clock, chỉ báo cáo), nhưng hai mục này chưa chạy. Mã E1-5 đã được dùng lại cho stress EoT.
- **Deserializer chung.** RX AMD dùng XPHY, RX mình dùng Block No. 1. Đặt cả hai sau cùng một deserializer là TN2c.
- **Packet CSI-2.** Dữ liệu là dummy, không có cấu trúc packet. Phần này thuộc TN2 và TN3.
- **Hiệu ứng analog.** Pad chỉ là mức logic, front end là model, không có jitter hay ISI. Hành vi AFE thật ở EoT
  vẫn là giả định (ADR-001).
- **Lỗi bit cố ý.** Không chèn lỗi bit vào sync hay payload. Nhiễu chỉ có ở LP-00 (E1-3g) và ở cuối trail
  (E1-5).
- **`stopstate`.** Có ghi trong CSV nhưng không so.

## 9. Cách chạy

Chạy từ thư mục gốc của repo. Output nằm ở `fpga/work/exp1/<tên kịch bản>/` (gitignored): `truth.txt`,
`xil_ppi.csv`, `ftel_ppi.csv`, `xsim.log`, `tb.txt` và `check.txt`.

```bash
fpga/exp1/run_exp1.sh all                  # E1-1..E1-5 ở chế độ công bằng, rồi bảng kết quả (~23 phút)
fpga/exp1/run_exp1.sh E1-3                 # một nhóm kịch bản
fpga/exp1/run_exp1.sh E1-5 400 600         # E1-5 ở một số rate (mỗi rate ~2,5 phút)
fpga/exp1/run_exp1.sh model                # bộ phụ M_*: mọi kịch bản, RX mình sau afe_model (~23 phút)
fpga/exp1/run_exp1.sh model E1-5 260       # bộ phụ, một nhóm hoặc một số rate
fpga/exp1/run_exp1.sh run 1440 4 <tên> +PATTERN=prbs9 +LENS=1,8,64   # một kịch bản tự chọn, cả hai RX
fpga/exp1/run_exp1.sh run 1440 4 <tên> +AFE=model                    # RX mình sau afe_model
fpga/exp1/run_exp1.sh run 600 stub <tên> +TRAIL=min +EOT_JUNK=40     # chỉ RX mình, rate bất kỳ
fpga/exp1/run_exp1.sh window               # đo cửa sổ eot_skip_bytes (~7 phút)
fpga/exp1/run_exp1.sh report               # R-80
fpga/exp1/run_exp1.sh summary              # dòng kết quả của mọi kịch bản đã chạy
fpga/exp1/run_exp1.sh recheck              # kiểm lại mọi output bằng csi2_dump.py hiện tại (~25 s, không mô phỏng)
python3 fpga/exp1/tn1_evidence.py          # kiểm chứng kết quả (§7)
fpga/exp1/neg_front.sh                     # phép thử âm của check front end (§7.6, ~1 phút)
```

- Mỗi tổ hợp rate × số lane cần một build Vivado: khoảng 5 phút lần đầu, vài giây khi chỉ testbench đổi.
- Một kịch bản chạy khoảng 10–15 s với cả hai RX, vài giây ở chế độ `stub`.
- Các lệnh trên các build khác nhau chạy song song được; hai lệnh không được dùng chung một build cùng lúc. Lần chạy
  2026-10-20 xong toàn bộ trong 13 phút:
  - pha 1: E1-1…E1-3, E1-4, R-80 với `window`, và E1-5 ở 400/600/1000/1200 Mb/s, mỗi nhóm một tiến trình;
  - pha 2: E1-5 ở 260/800/1440/1500 Mb/s;
  - mỗi tiến trình chạy chế độ công bằng rồi tới bộ `model`.
- Danh sách plusarg (front end, timing, skew, pattern, nhiễu, seed) nằm ở đầu [`tb_exp1.sv`](tb_exp1.sv).
