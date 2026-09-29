# ftel_dphy_rx — Câu hỏi cho team CSI-2 Rx controller

| Mục | Nội dung |
|---|---|
| Gửi | Team CSI-2 Rx controller (HAS-CSI = `FTEL_IP_MIPI_CSI-2_CONTROLLER_HAS_v1.2.docx`) |
| Từ | Nhóm thiết kế D-PHY Rx (`ftel_dphy_rx`) |
| Ngày | 2026-09-26, cập nhật 2026-09-29 (thêm ADR-006; K3 thêm `eot_skip_bytes`) |
| Căn cứ | HAS của `ftel_dphy_rx` bản nháp v0.6 (`hw/rtl/ip/ftel_dphy_rx/doc/spec.md`), HAS-CSI v1.2 |

## Bối cảnh

`ftel_dphy_rx` là khối "D-PHY macro" trong HAS-CSI. Khối này nhận các lane từ AFE (analog) và xuất
dữ liệu cho CSI-2 Rx controller qua PPI theo HAS-CSI Table 4-3. Chúng tôi dùng HAS-CSI làm hợp đồng
PPI. Phụ lục ở cuối file ghi lại cách chúng tôi hiểu HAS-CSI (C1–C16); nhờ team kiểm giúp.

Mỗi câu hỏi kèm **giả định đang dùng**. Thiết kế sẽ đi theo giả định đó cho tới khi có câu trả lời.
Nếu team đồng ý với giả định, chỉ cần trả lời "Đồng ý".

**Cần trả lời trước HAS v1.0** (chưa có thì chưa sinh RTL được): **K1, K3, K6, ADR-006**.

## Tóm tắt

| ID | Chủ đề | Ưu tiên | Yêu cầu đang chờ |
|---|---|---|---|
| K1 | Tốc độ lane tối đa; bản phát hành của 4K staggered HDR; `rxskewcalhs_x` khi chưa calibrate | **Cao** | 5 |
| K2 | Các cổng LPDT | Trung bình | 8 |
| K3 | Nơi cấu hình timer của D-PHY; lập trình theo tốc độ lane | **Cao** | 6 |
| K4 | Ngân sách lệch byte giữa các lane | Trung bình | 1 |
| K5 | Register map v1.4 | Trung bình | 2 |
| K6 | `phy_core_rst`, `init_done`, `forcerxmode_x` | **Cao** | 3 |
| K7 | Sửa dẫn chiếu trong HAS-CSI (biên tập) | Thấp | — |
| K8 | Burst HS dài nhất trên một lane | Trung bình | 2 |
| F-001 | Thời gian giữ `errcontrol_x` khi lỗi do chính LP-11 gây ra | Trung bình | 1 |
| ADR-006 | EoT: thứ tự `stopstate_x` / `rxactivehs_x`, byte trailer sau packet ở tốc độ thấp, độ trễ PPI | **Cao** | 7 |

---

## K1 — Tốc độ lane, deskew và bản phát hành

**Câu hỏi.**
1. Tốc độ tối đa mỗi lane mà D-PHY phải hỗ trợ là bao nhiêu? HAS-CSI §1 ghi "up to 1500 Mbps", còn
   Table 4-1 và §7.1 ghi 1792 Mb/s (`rxbyteclkhs` 224 MHz).
2. Chế độ 4K staggered HDR RAW12 (1493–1528 Mb/s/lane chưa tính blanking, HAS-CSI §7.3) cần ngay
   trong bản đầu tiên, hay ở bản sau?
3. Lane của IMX274 trên board FPGA chạy ở tốc độ bao nhiêu?
4. Ở bản chưa có calibrate deskew, D-PHY vẫn nhận ra deskew burst (sync toàn bit 1). Khi đó D-PHY bật
   `rxskewcalhs_x` cho tới khi lane về Stop, và không phát `rxvalidhs_x` hay `rxsynchs_x` trong burst
   đó (C9). Controller có chấp nhận cách này không? Hay controller muốn `rxskewcalhs_x` luôn bằng 0,
   như trường hợp macro không có deskew mà HAS-CSI §4.3.1 cho phép?

**Vì sao cần.**
- Trên 1.5 Gb/s, HAS-CSI §7.1 bắt buộc deskew theo D-PHY v1.2. Điều này kéo theo một khối Deskew
  Controller riêng và một delay line trong AFE.
- `rxbyteclkhs` 224 MHz là rủi ro timing trên công nghệ GF 130 nm.
- Câu 4 quyết định hành vi của `rxskewcalhs_x` ở bản đầu. Nếu buộc 0, một deskew burst sẽ hiện ra
  như một burst lỗi sync (`errsotsynchs_x`).

**Giả định hiện tại.**
- R1: 80–1500 Mb/s. D-PHY nhận ra và báo deskew burst trên `rxskewcalhs_x`, không calibrate.
- R2: 80–1792 Mb/s, calibrate deskew.

**Tham chiếu.** HAS-CSI §1, §4.3.1, §7.1, §7.3, Table 4-1. HAS D-PHY §1.4, ADR-003.

## K2 — Các cổng LPDT

**Câu hỏi.**
1. D-PHY không làm Low-Power Data Transmission (LPDT) trong bản đầu. Các cổng `rxlpdtesc_x`,
   `rxdataesc_x[7:0]`, `rxvalidesc_x` và `errsyncesc_x` có được buộc về 0 không?
2. Nếu sau này cần LPDT thì các cổng này thuộc domain nào: `core_clk` như AMD PG202, hay RxClkEsc
   như D-PHY Annex A?

**Vì sao cần.** HAS-CSI Table 4-3 có khai báo các cổng LPDT, nhưng controller không dùng chúng (C12).

**Giả định hiện tại.**
- Buộc 0, với tham số tổng hợp `PARA_LPDT_EN` = 0.
- D-PHY vẫn xuất `rxclkesc_x`, bằng XOR của hai đường LP đã đồng bộ. Không có logic nào trong D-PHY
  chạy bằng clock này.

**Tham chiếu.** HAS-CSI Table 4-3. HAS D-PHY §3 (#5), §5.1.

## K3 — Nơi cấu hình timer của D-PHY

**Câu hỏi.**
1. Các giá trị cấu hình của D-PHY sẽ đặt ở đâu? Có hai lựa chọn:
   - thêm trường vào register map v1.4 của controller (PHY_CONFIG, …);
   - D-PHY có bus cấu hình riêng. Nếu vậy, bus đó chạy bằng clock nào?
2. `hs_settle_cyc` phụ thuộc tốc độ lane. Driver có lập trình được giá trị theo tốc độ **trước khi
   enable lane** không? Giá trị tính sẵn, theo chu kỳ `core_clk` 5 ns:

   | Tốc độ | `hs_settle_cyc` |
   |---|---|
   | 80 Mb/s | 39 |
   | 750 Mb/s | 21 |
   | 1500 Mb/s | 20 |
   | 1792 Mb/s | 20 |

3. D-PHY yêu cầu chỉ đổi cấu hình khi lane liên quan đang tắt (`cl_enable` / `dl_enable_x` = 0).
   Ràng buộc này có hợp với trình tự bring-up của controller không?

**Các trường cần đặt.**

| Trường | Mặc định |
|---|---|
| `hs_settle_cyc` | 20 |
| `clk_settle_cyc` | 36 |
| `tinit_cyc` | 20 000 (100 µs) |
| `hs_rx_timeout_cyc` | 2^18 (≈ 1.31 ms) |
| `esc_timeout_cyc` | 2^18 |
| `eot_skip_bytes` | 16 (ở 1500 Mb/s); phụ thuộc tốc độ, lập trình cùng `hs_settle_cyc` |
| Đảo cực P/N, map lane | Không đảo, thẳng |
| `deskew_bypass` | Chỉ có ở R2 |

Status gồm trạng thái FSM của từng lane, cùng các cờ sticky có bộ đếm cho: lỗi EoT sync, HS RX
timeout, lỗi SoT, lỗi escape, escape timeout, và request bị hủy trên clock lane.

**Vì sao cần.** THS-SETTLE có cửa sổ 85 ns + 6·UI … 145 ns + 10·UI (D-PHY Table 14), nên một giá trị
cố định chỉ đúng cho một tốc độ.

**Giả định hiện tại.** D-PHY có APB subordinate riêng; giá trị reset tính cho 1500 Mb/s. Các phương
án đã được chấm điểm:

| Phương án | Điểm |
|---|---|
| A: thêm trường vào CSR của controller | 42 |
| **B: APB riêng** | **55** |
| C: chỉ dùng tham số tổng hợp | 34 |

**Tham chiếu.** HAS D-PHY §3, §4.10, §5.3, ADR-005, Appendix B.

## K4 — Ngân sách lệch byte giữa các lane

**Câu hỏi.**
1. Xác nhận lệch tối đa giữa các lane tại PPI là `SKEW_DEPTH` − `FIFO_AF_MARGIN` = 6 chu kỳ
   `rxbyteclkhs` (HAS-CSI Table 3-1 #3, #4).
2. Lệch này đo từ sự kiện nào? Ví dụ: từ `rxsynchs_x` của lane đến sớm nhất tới lane đến muộn nhất
   trong cùng một burst.
3. Ngân sách 6 chu kỳ có tính cả lệch do board và AFE không?

**Vì sao cần.** D-PHY không có FIFO bù lệch giữa các lane; việc gộp lane là của controller. Vì vậy
lệch tại PPI bằng lệch đầu vào (Tx, board, AFE), làm tròn theo byte. Test tích hợp sẽ kiểm con số này.

**Giả định hiện tại.** ≤ 6 chu kỳ, đo giữa các xung `rxsynchs_x` của cùng một burst.

**Tham chiếu.** HAS-CSI Table 3-1. HAS D-PHY §8 (Integration).

## K5 — Register map v1.4

**Yêu cầu.** Nhờ team gửi file `FTEL_MEMORY_MAP_REGISTERS_v1_4.xlsx`, đặc biệt các trường
PHY_CONFIG, PHY_STATUS, LANE_STATUS.

**Vì sao cần.** Để các trường status của D-PHY (xem K3) khớp với register của controller và không
trùng chức năng. Mục Registers (§6) của HAS D-PHY đang hoãn cho tới khi có file này.

## K6 — `phy_core_rst`, `init_done`, `forcerxmode_x`

**Câu hỏi.**
1. `phy_core_rst` là active High hay active Low? Đồng bộ hay bất đồng bộ? Nếu đồng bộ thì theo clock
   nào?
2. Theo FX1 IP Wrapper Guideline, mọi port reset ở wrapper là active-low (`_n`); reset active-high thì
   đặt inverter bên trong wrapper. `phy_core_rst` là một bit CSR của controller. Nó có được coi là
   port loại RESET không? Bit CSR đó có cực tính nào?
3. `init_done` lên khi clock lane và mọi data lane đang enable đã khởi tạo xong (LP-11 liên tục
   ≥ TINIT). Khi một lane bị tắt rồi bật lại, hoặc khi `forcerxmode_x` được bật, `init_done` có phải
   hạ xuống không?
4. `forcerxmode_x` là mức hay xung? Có phải chỉ được bật khi lane đang ở Stop state không?

**Vì sao cần.** Cực tính và kiểu reset quyết định mạch đồng bộ reset trong từng clock domain và
cách khai port ở wrapper `m_ftel_dphy_rx_wrap`.

**Giả định hiện tại.**
- `phy_core_rst` active High. Assert bất đồng bộ; release đồng bộ theo từng domain bên trong D-PHY.
- Controller giữ `phy_core_rst` ≥ 40 chu kỳ `core_clk` (C14).
- Ở wrapper: port active-low `_n`, inverter đặt trong `m_ftel_dphy_rx_wrap`.
- Hành vi của `init_done` khi khởi tạo lại một lane chưa được định nghĩa trong bản nháp.

**Tham chiếu.** HAS-CSI Table 4-3 (#1–#3, #28–#29), mục "Bring-up". HAS D-PHY §4.2, §4.7.

## K7 — Sửa dẫn chiếu trong HAS-CSI (biên tập)

Không cần quyết định; nhờ team sửa trong bản HAS-CSI kế tiếp:
- Bảng revision ghi V0.1, bìa ghi V1.2.
- Phần bring-up dẫn "Table 4-3", nhưng nội dung đó nằm ở Table 4-2.
- §5 dẫn "Table 4-1" cho PPI.
- Các mục "4.3.4" và "4.2.4" được dẫn tới nhưng không tồn tại.

## K8 — Burst HS dài nhất trên một lane

**Câu hỏi.** Xét mọi sensor mode và mọi tổ hợp số lane/tốc độ, burst HS dài nhất trên một lane dài
bao nhiêu (tính bằng byte, hoặc µs)?

**Vì sao cần.** Controller không có timeout cho `rxactivehs_x` bị kẹt (C11). Vì vậy D-PHY có HS RX
timeout để bảo đảm `rxactivehs_x` luôn hạ. Timeout này phải dài hơn burst dài nhất; nếu ngắn hơn,
D-PHY sẽ cắt một burst hợp lệ.

**Giả định hiện tại.** Burst dài nhất là một dòng 5802 byte ở 80 Mb/s trên 1 lane, khoảng 580 µs.
Timeout đặt 2^18 chu kỳ `core_clk`, khoảng 1.31 ms.

**Tham chiếu.** HAS-CSI §4.4.5 ("Stuck state"). HAS D-PHY §3 (`hs_rx_timeout_cyc`), §4.6.

## F-001 — `errcontrol_x` khi lỗi do chính LP-11

**Câu hỏi.**
- Data lane có thể đang ở giữa một chuỗi request (sau LP-10 hoặc LP-01) thì gặp LP-11. Khi đó D-PHY
  báo false control, tức bật `errcontrol_x`, rồi đưa lane về Stop ngay trên chính LP-11 đó.
- HAS-CSI yêu cầu `errcontrol_x` giữ tới lần đổi trạng thái đường truyền kế tiếp (C13). Vì vậy sẽ có
  một khoảng thời gian `stopstate_x` = 1 và `errcontrol_x` = 1 cùng lúc, kéo dài tới request kế tiếp.
- Controller có chấp nhận trạng thái "Stop + `errcontrol_x` = 1" này không?

**Giả định hiện tại.** Có. `errcontrol_x` hạ ở lần đổi trạng thái đường truyền đầu tiên sau LP-11
đó.

**Tham chiếu.** HAS-CSI Table 4-3 (#24–#26). HAS D-PHY §4.5 (luật thứ tự ưu tiên của FSM data lane).

## ADR-006 — EoT ở tốc độ thấp

**Câu hỏi.**
1. HAS-CSI Figure 4-1 cho `stopstate_x` lên trong khoảng từ byte cuối trở đi. Sau EoT, D-PHY có thể bật
   `stopstate_x` sớm hơn thế, tối đa `PARA_EOT_DELAY_BYTES` chu kỳ `rxbyteclkhs` trước khi byte cuối
   ra PPI (3.2 µs ở 80 Mb/s), tức là trước khi `rxactivehs_x` hạ. Controller có chấp nhận thứ tự này
   không? Controller có dùng `stopstate_x` để nhận biết burst đã kết thúc không?
2. Dưới khoảng 270 Mb/s, D-PHY không bảo đảm cắt trailer đúng tới từng byte. Nếu D-PHY cắt muộn, vài
   byte trailer sẽ ra sau packet footer với `rxvalidhs_x` = 1. HAS-CSI tìm cuối packet theo Word
   Count; controller có bỏ qua các byte sau footer không, hay coi đó là lỗi?
3. Dữ liệu ra PPI trễ `PARA_EOT_DELAY_BYTES` chu kỳ `rxbyteclkhs` so với đường truyền: 32 chu kỳ, tức
   3.2 µs ở 80 Mb/s và 0.17 µs ở 1500 Mb/s. Controller có ràng buộc nào về độ trễ này không?

**Vì sao cần.**
- D-PHY phải giữ lại đuôi burst trong một delay line để cắt trailer (D-PHY §6.4.3). Khi LP-11 xuất
  hiện, yêu cầu EoT phải đi qua `core_clk` rồi sang `rxbyteclkhs`, nên thời điểm LP-11 chỉ biết được
  với sai số cỡ một chu kỳ byte clock. Ở tốc độ thấp, sai số này lớn hơn khoảng an toàn mà D-PHY để
  lại giữa trailer và LP-11.
- Lane đợi D-PHY cắt xong (EoT done) rồi mới về Stop. EoT done được gửi ngay khi cắt xong, trước khi
  delay line xả hết, nên `stopstate_x` lên trước khi byte cuối ra PPI (câu 1). Nếu controller cần
  đúng thứ tự của Figure 4-1, D-PHY phải đợi xả hết delay line mới về Stop. Khi đó, dưới khoảng
  1.2 Gb/s, lane bỏ lỡ burst kế tiếp nếu Tx dùng THS-EXIT và TLPX ở mức tối thiểu.
- Câu 2 quyết định hướng xử lý ở tốc độ thấp: nghiêng về cắt muộn (thừa byte), hay phải đo thêm
  thời điểm LP-11 ở mức dưới một byte (phức tạp hơn).

**Giả định hiện tại.**
- Lane đợi EoT done rồi mới về Stop (đã chốt). Hệ quả phía Tx: dưới khoảng 240 Mb/s, hai burst liền
  nhau cần THS-EXIT + TLPX lớn hơn khoảng 32·UI + 15 ns (HAS D-PHY §4.5). Phần này đã hỏi phía Tx.
- `stopstate_x` có thể lên trước byte cuối như ở câu 1, cho tới khi team trả lời.
- Cắt trailer chính xác trên khoảng 270 Mb/s. Dưới mức đó chưa chốt (ADR-006).

**Tham chiếu.** HAS D-PHY §4.5 và §4.6 (các design note), ADR-006, §9. HAS-CSI Figure 4-1, Table 4-3,
§4.4 (`err_wc` chỉ báo khi thiếu byte).

---

## Phụ lục — Cách chúng tôi hiểu HAS-CSI (nhờ xác nhận hoặc sửa)

| # | Ràng buộc | Nguồn trong HAS-CSI |
|---|---|---|
| C1 | Nền tảng: CSI-2 v1.3 + D-PHY v1.2 | §1 |
| C2 | 1/2/4 data lane + 1 clock lane; `MAX_LANES` = 4; không hỗ trợ 3 hay 8 lane | Table 3-1, §7.1 |
| C3 | PPI 8 bit/lane (`rxdatahs_x[7:0]`, bit 0 là bit nhận trước); một `rxbyteclkhs` chung = HS DDR clock / 8 | Table 4-3 |
| C4 | Giới hạn 1792 Mb/s/lane; trên 1.5 Gb/s bắt buộc deskew v1.2 (xem K1) | Table 4-1, §4.3.1, §7.1 |
| C5 | Chỉ continuous clock; `cl_rxclkactivehs` dùng để chẩn đoán | §4.3.1 |
| C6 | `rxsynchs_x` là xung 1 chu kỳ, cùng chu kỳ với byte payload đầu tiên | Table 4-4 |
| C7 | `rxvalidhs_x` được phép có khoảng trống trong burst | §4.3.3, §4.4.5 |
| C8 | Khi có `errsotsynchs_x`: không có `rxsynchs_x`, `rxvalidhs_x` giữ 0 suốt burst, `rxactivehs_x` vẫn giữ tới EoT. `errsoths_x` là xung 1 chu kỳ, burst vẫn dùng được | §4.3.3 |
| C9 | `rxskewcalhs_x` bật khi nhận ra sync toàn bit 1, giữ tới khi lane về Stop; không có `rxvalidhs_x`/`rxsynchs_x` trong deskew burst; không dùng RxErrorCalHS | §4.3.1, §4.3.3 |
| C10 | Lệch byte giữa các lane tại PPI tối đa 6 chu kỳ `rxbyteclkhs` (xem K4) | Table 3-1 |
| C11 | Controller không có timeout cho `rxactivehs_x` bị kẹt, nên D-PHY phải bảo đảm `rxactivehs_x` luôn hạ (xem K8) | §4.4.5 |
| C12 | Escape: báo ULPS và Trigger bất đồng bộ, giữ tới khi về Stop; các cổng LPDT có khai báo nhưng không dùng (xem K2) | Table 4-3 |
| C13 | Lỗi LP (`erresc_x`, `errsyncesc_x`, `errcontrol_x`) bất đồng bộ, giữ tới lần đổi trạng thái đường truyền kế tiếp (xem F-001) | Table 4-3 |
| C14 | `cl_enable`, `dl_enable_x`, `forcerxmode_x` là tín hiệu mức từ CSR (domain `lite_aclk`); `phy_core_rst` rộng ≥ 40 chu kỳ `core_clk`; D-PHY trả `init_done` trong domain `core_clk` (xem K6) | Table 4-3 |
| C15 | `core_clk` 200 MHz chạy tự do, cấp thẳng từ hệ thống vào D-PHY | Table 4-1, Table 4-3 |
| C16 | Bring-up chỉ dựa vào Stop state: reset D-PHY → enable → chờ `stopstate` trên mọi lane (Tx giữ LP-11 ≥ TINIT) | §4.3.3 "Bring-up" |

## Trả lời

| ID | Trả lời | Người trả lời | Ngày |
|---|---|---|---|
| K1 | | | |
| K2 | | | |
| K3 | | | |
| K4 | | | |
| K5 | | | |
| K6 | | | |
| K7 | | | |
| K8 | | | |
| F-001 | | | |
| ADR-006 | | | |
| Phụ lục C1–C16 | | | |
