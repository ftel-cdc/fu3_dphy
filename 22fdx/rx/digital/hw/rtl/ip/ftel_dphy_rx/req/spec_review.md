# ftel_dphy_rx — Spec review (Stage A, P1)

| Mục | Giá trị |
|---|---|
| Spec | `hw/rtl/ip/ftel_dphy_rx/doc/spec.md`, **DRAFT v0.3**, sha256 `fe0d2645cb8e77edd4dd2d338de6ee3b5ddc7e1fc1bf05ef440f47ca06a7d343` |
| Artifact | `req/structured_spec.json`, sha256 `2968f01250d23f593b502271a5346f1ebbc01bc51ba91d62954a3e91f954bd84` |
| Cách tạo | `/dphy_autoflow --to P1 --mode review` → `dphy_spec_parse` (11 chunk) → `assemble_req.py` → `validate_req.py` → `flow_check.py` |
| Gate 1 | `draft` — **chưa ký**, vì spec còn là bản nháp và còn 37 REQ cần quyết định |
| Ngày | 2026-09-26 |
| Kế hoạch | `doc/RTL_FLOW_PLAN.md`, bước A7 |

Ký hiệu: ✅ đã kiểm bằng tool · ⚠️ giả định / đề xuất · 🔍 cần kiểm thêm.

---

## 1. Kết quả chấm máy (a)

Bảng dưới đây in nguyên văn output của lệnh:

```bash
python3 hw/utils/req_flow/validate_req.py hw/rtl/ip/ftel_dphy_rx/req/structured_spec.json \
        --spec hw/rtl/ip/ftel_dphy_rx/doc/spec.md --report-md        # exit 0
```

| Metric | Value |
|---|---|
| requirements | 190 |
| findings | 5 |
| quote_match | 195/195 |
| needs_review | 58 |
| needs_human_decision | 37 |
| warnings | 0 |
| by_category | clocking: 9, constraint: 14, decision: 25, functional: 51, interface: 48, parameter: 15, reset: 3, timing: 12, verification: 13 |
| by_block | No.1: 26, No.2: 21, No.3: 39, No.4: 30, No.5: 8, No.6: 15, No.7: 11, No.8: 10, all: 30 |
| by_spec_status | assumed: 18, contract: 47, design: 62, open: 31, verified: 32 |
| by_release | R1: 3, R2: 6, both: 181 |
| coverage | afe: 8/8, c_ids: 15/15, cdc: 5/5, clock: 3/3, fsm_cl: 10/10, fsm_dl: 16/16, open: 10/10, param: 10/10, ppi: 29/29, q_ids: 9/9, reset: 3/3, runtime: 5/5, timing: 9/9 |
| issues_by_code | none |

Đối chiếu với tiêu chí A5 trong kế hoạch:

| Tiêu chí A5 | Yêu cầu | Kết quả | |
|---|---|---|---|
| Schema | 0 lỗi | 0 | ✅ |
| Trích dẫn nguyên văn | 100% | 195/195 (190 REQ + 5 finding) | ✅ |
| Độ phủ inventory | 100% cho PPI, FSM, param, runtime, timing, open items | 100% ở cả 13 nhóm, gồm Q-ID 9/9 và C-ID 15/15 | ✅ |
| Luật nhất quán (OPEN, ⚠️, cờ review) | 0 vi phạm | 0 | ✅ |
| Số vòng sửa | ≤ 2 | Đạt ngay vòng đầu | ✅ |

Kiểm chứng bổ sung:

- ✅ `flow_check.py --phase P1 --mode review`: 0 xung đột (`req/conflicts_P1.json`). 37 REQ `needs_human_decision` chỉ được báo ở mức thông tin, đúng chính sách của chế độ review.
- ✅ Cùng artifact chạy ở `--mode gate`: flow **dừng** với 37 CF-OPEN (exit 2). Nghĩa là Gate 1 bị chặn máy cho tới khi các mục ở §2 được quyết định.
- ✅ Bộ test âm A8 (`flow_check.py --selftest-negative`, chạy trên bản sao): **6/6 PASS**. Gồm 1 run sạch và 5 đột biến:

  | Đột biến | Mã bắt được |
  |---|---|
  | Sửa 1 byte của spec | CF-SPEC |
  | Sửa 1 `source_quote` | CF-QUOTE |
  | Waiver cho CF-QUOTE | Bị từ chối |
  | Xóa REQ của 1 tín hiệu PPI | CF-COVER |
  | Bỏ cờ của REQ OPEN ở chế độ gate | CF-OPEN |

## 2. Các mục cần người quyết định, nhóm theo chủ (b)

### 2.1 Tổng hợp

| Chủ | Mục mở (số REQ) | Tổng REQ | Kênh sync hiện có |
|---|---|---|---|
| CSI team | K1 (5) · K2 (7) · K3 / ADR-005 (5) · K4 (1) · K5 (2) · K6 (2) | 22 | Research plan §5.2 (K1–K7) |
| AFE team | ADR-001 (7, trong đó REQ-032 dính thêm ADR-004) | 7 | **Chưa có danh sách riêng** — xem đề xuất D2 ở §4 |
| Tx side | S4 (3, trong đó REQ-101 dính thêm ADR-004) · S5 (2) | 5 | Research plan §5.1 (S1–S11) |
| Nội bộ | T1 (2) · ADR-004 (1) | 3 | Kiểm lại D-PHY v1.1 Table 8 (T1); ADR-004 chờ AFE |
| **Tổng** | | **37** | |

Quy tắc gán chủ: một REQ tham chiếu nhiều mục thì theo thứ tự ưu tiên CSI > AFE > Tx > nội bộ. Ví dụ REQ-032 (ADR-004, ADR-001) thuộc AFE; REQ-151 (K5, ADR-005) thuộc CSI.

**Thứ tự nên chốt** (xếp theo số REQ được giải quyết):

1. **K2**: 7 REQ, toàn bộ là tie-off của các cổng LPDT.
2. **ADR-001**: 7 REQ; đồng thời là điều kiện vào của Stage B4 (AFE model).
3. **K1**: 5 REQ; quyết định có Block No. 5 (deskew) trong R1 hay không.
4. **K3 / ADR-005**: 5 REQ; quyết định cấu trúc Block No. 8.

Tổng cộng bốn mục này giải quyết 24/37 REQ.

### 2.2 CSI team — 22 REQ

| REQ | Dòng | Block | Mục mở | Nội dung |
|---|---|---|---|---|
| REQ-005 | 136 | all | K1 | The release plan (R1 without deskew calibration, R2 with calibration) is a proposal pending K1; the target line rate per release must be confirmed by the CSI team. |
| REQ-006 | 140 | all | K1 | Release R1 shall support 80-1500 Mb/s per lane, detect deskew bursts and flag them on rxskewcalhs_x, without deskew calibration. |
| REQ-007 | 141 | No.5 | K1 | Release R2 shall support 80-1792 Mb/s per lane with deskew calibration active (Block No. 5) for 4K staggered HDR RAW12. |
| REQ-155 | 518 | all | K1 | Release staging shall be R1 without deskew calibration and R2 with it; this is pending K1. |
| REQ-171 | 573 | all | K1 | The target line rate (1500 or 1792 Mb/s) and the release of 4K staggered HDR shall be decided with the CSI team; default R1 <= 1500 Mb/s. |
| REQ-012 | 152 | No.3 | K2 | Low-Power Data Transmission (LPDT) reception shall not be part of R1; the treatment of the LPDT PPI ports is pending K2. |
| REQ-027 | 228 | No.3 | K2 | PARA_LPDT_EN (default 0) shall instantiate LPDT reception; when 0 the LPDT PPI outputs shall be tied inactive. The default is pending K2. |
| REQ-131 | 444 | No.7 | K2 | rxlpdtesc_x shall be a 1-bit output in core_clk tied to 0 while LPDT is not implemented (pending K2). |
| REQ-134 | 447 | No.7 | K2 | rxdataesc_x shall be an 8-bit output in core_clk tied to 0 while LPDT is not implemented (pending K2). |
| REQ-135 | 448 | No.7 | K2 | rxvalidesc_x shall be a 1-bit output in core_clk tied to 0 while LPDT is not implemented (pending K2). |
| REQ-139 | 452 | No.7 | K2 | errsyncesc_x shall be a 1-bit asynchronous output tied to 0 because LPDT is not implemented (pending K2). |
| REQ-172 | 574 | No.7 | K2 | The tie-off and clock domain of the LPDT PPI ports shall be agreed with the CSI team; default tied 0. |
| REQ-022 | 214 | No.8 | K3, ADR-005 | Block No. 8 (Configuration & Status) shall run in a configuration clock whose source depends on the open configuration path (K3). |
| REQ-040 | 255 | No.8 | ADR-005, K3 | Block No. 8 shall use a configuration clock whose source and frequency depend on the configuration path (ADR-005, K3). |
| REQ-110 | 413 | No.8 | K3, ADR-005 | The bus and register map of Block No. 8 are open (K3, ADR-005). |
| REQ-150 | 473 | No.8 | K3, ADR-005 | The configuration and status interface is open (K3, ADR-005); the draft assumes a dedicated APB subordinate in Block No. 8. |
| REQ-173 | 575 | No.8 | K3, ADR-005 | The configuration path of the timers shall be agreed with the CSI team; default own APB subordinate (ADR-005). |
| REQ-174 | 576 | all | K4 | The inter-lane byte divergence budget at the PPI shall be confirmed with the CSI team; default <= 6 byte cycles. |
| REQ-151 | 480 | No.8 | K5, ADR-005 | The register map is deferred until ADR-005 is agreed and the CSI-2 controller register map (FTEL_MEMORY_MAP_REGISTERS_v1_4.xlsx, K5) is available. |
| REQ-175 | 577 | No.8 | K5 | Register map v1.4 (PHY_CONFIG, PHY_STATUS, LANE_STATUS) shall be obtained from the CSI team. |
| REQ-046 | 271 | all | K6 | phy_core_rst shall reset the whole IP (asynchronous assert, synchronous release per domain), be asserted for at least 40 core_clk cycles by the CSI-2 controller, and restart initialization of every lane on release; its polarity and synchronicity are pending K6 (draft: active High, asynchronous). |
| REQ-176 | 578 | all | K6 | The polarity and synchronicity of phy_core_rst and the exact semantics of init_done and forcerxmode_x shall be agreed with the CSI team; default active High, asynchronous. |

### 2.3 AFE team — 7 REQ

| REQ | Dòng | Block | Mục mở | Nội dung |
|---|---|---|---|---|
| REQ-003 | 68 | No.1 | ADR-001 | The AFE (analog, outside this IP) shall receive the HS and LP line levels and provide termination and deserialization; its exact boundary with this IP is open (ADR-001). |
| REQ-053 | 288 | No.1 | ADR-001 | The termination enable shall be issued on LP-00 detection without an extra timer so that TD-TERM-EN (<= 35 ns + 4 UI) and TCLK-TERM-EN (<= 38 ns) are met with the ~20 ns digital latency; if the AFE cannot meet the remaining budget, termination switching moves into the AFE (ADR-001). |
| REQ-065 | 313 | No.2 | ADR-001 | Loss of the HS clock shall be detected within TCLK-MISS (<= 60 ns) at every supported rate; because rxbyteclkhs alone cannot do this at 80 Mb/s, clock-activity detection is expected from the AFE (afe_cl_clk_active) or the requirement is relaxed for low rates, to be decided with ADR-001. |
| REQ-141 | 457 | No.1 | ADR-001 | The AFE interface shall assume that the AFE delivers deserialized, unaligned 8-bit words per lane on a common byte clock (ADR-001 option B); the boundary is open with the AFE team. |
| REQ-152 | 500 | No.1 | ADR-001 | The AFE boundary (proposed option B) shall still be agreed with the AFE team, including clock-activity detection (TCLK-MISS), termination timing and the delay-tap interface. |
| REQ-177 | 579 | No.1 | ADR-001 | The AFE boundary, clock-activity detection, termination timing and delay taps shall be agreed with the AFE team; default option B. |
| REQ-032 | 233 | No.5 | ADR-004, ADR-001 | PARA_DLY_TAP_WIDTH shall set the width of the AFE delay-tap control used by deskew calibration; its value is still to be determined with ADR-004. |

### 2.4 Tx side — 5 REQ

| REQ | Dòng | Block | Mục mở | Nội dung |
|---|---|---|---|---|
| REQ-090 | 360 | No.4 | S4 | In R1 and R2 a run of at least 16 ones after HS-0 (v1.2 skew-calibration sync) shall assert rxskewcalhs_x until the lane returns to Stop, with no rxvalidhs_x or rxsynchs_x during that burst; in R2 the burst is forwarded to Block No. 5. The exact pattern depends on the Tx deskew behaviour (S4). |
| REQ-101 | 390 | No.5 | ADR-004, S4 | Block No. 5 shall receive the deskew bursts identified by Block No. 4, drive the AFE delay taps of its lane and select the tap in the centre of the passing window. |
| REQ-178 | 580 | No.4 | S4 | The Tx deskew behaviour (initial or periodic, exact pattern) shall be confirmed by the Tx side; default D-PHY v1.2 pattern from a secondary source. |
| REQ-030 | 231 | No.4 | S5 | PARA_EOT_DELAY_BYTES (default 32, assumption) shall size the EoT delay line of Block No. 4 to cover THS-TRAIL + THS-SKIP + LP-11 detection latency at the highest line rate; the value depends on the Tx timing table (S5). |
| REQ-179 | 581 | No.4 | S5 | The Tx timing table, in particular the maximum THS-TRAIL that sizes PARA_EOT_DELAY_BYTES, shall be obtained from the Tx side; default specification minimums. |

### 2.5 Nội bộ — 3 REQ

| REQ | Dòng | Block | Mục mở | Nội dung |
|---|---|---|---|---|
| REQ-084 | 345 | No.3 | T1 | The four trigger entry commands of D-PHY Table 8 shall be mapped to rxtriggeresc_x[3:0] in the order of Table 8; this mapping is an assumption to be confirmed (T1). |
| REQ-180 | 582 | No.3 | T1 | The mapping of the four trigger commands to rxtriggeresc_x[3:0] shall be checked against the specification; default order of D-PHY Table 8. |
| REQ-102 | 392 | No.5 | ADR-004 | The deskew algorithm, tap resolution and use of periodic calibration shall be decided for R2 (ADR-004), once the AFE delay-line capability is known. |

## 3. Chỗ mơ hồ mới, chưa có trong §9 của spec (c)

Nguồn của finding:

- **§3.1:** lần trích chính (P1).
- **§3.2:** lần trích độc lập A6 (clean-room).

Mọi finding đều có trích dẫn nguyên văn đã được validator kiểm: P1 5/5, A6 19/19. Cột "Đề xuất" là default ⚠️. Chưa có thay đổi nào được áp vào spec.

### 3.1 Từ lần trích chính (P1)

| ID | Dòng | Loại | Vấn đề | Đề xuất | Chủ |
|---|---|---|---|---|---|
| F-001 | 352 | Mơ hồ | §4.6 mô tả phép tìm sync vừa là "2-word window", vừa bị giới hạn bởi `PARA_SYNC_SEARCH_BYTES`. Spec không nói "2-word" là cửa sổ so sánh trong mỗi chu kỳ còn `PARA_SYNC_SEARCH_BYTES` là thời lượng tìm tối đa, cũng không nói bộ đếm bắt đầu từ lúc nào. Trích: *"searches a 2-word window for the"* | "2-word window" = cửa sổ so của barrel shifter trong mỗi chu kỳ. Phép tìm kéo dài tối đa `PARA_SYNC_SEARCH_BYTES` chu kỳ byte clock, đếm từ tín hiệu HS entry trong domain `rxbyteclkhs` | Nội bộ |
| F-002 | 401 | Mơ hồ | §4.9 buộc mọi output của lane có enable = Low về giá trị inactive. Nhưng các output PPI thuộc domain `rxbyteclkhs` (`rxactivehs_x`, `rxvalidhs_x`, `rxsynchs_x`, `rxdatahs_x`) không thể được cập nhật bằng logic có clock khi byte clock đang dừng (clock lane ở ULPS, hoặc lane bị tắt trước khi vào HS). Trích: *"Forces the inactive value of every output of a lane whose enable is Low"* | Gate tổ hợp các output PPI domain `rxbyteclkhs` bằng enable đã đồng bộ, đặt ở tầng output, để giá trị inactive giữ được mà không cần byte clock chạy. Thêm một dòng CDC cho enable đi vào mạch gate này | Nội bộ |
| F-003 | 408 | Không nhất quán | §4.10 liệt kê *"`PARA_DESKEW_EN` run-time bypass (R2)"* là trường cấu hình, trong khi §3 định nghĩa `PARA_DESKEW_EN` là tham số synthesis-time (quyết định có instantiate Block No. 5 hay không). Bypass lúc chạy cần một trường register riêng | Giữ `PARA_DESKEW_EN` là synthesis-time. Thêm trường run-time `deskew_bypass` trong Block No. 8 (R2); khi bật thì giữ tap ở giá trị reset | Nội bộ |
| F-004 | 578 | Câu hỏi | K6 nay còn phụ thuộc thêm FX1 IP Wrapper Guideline: mọi port reset của wrapper là active-low `_n`, reset active-high thì đặt inverter trong wrapper. Spec chưa nói `phy_core_rst` (do CSR của CSI-2 controller lái, không phải CRM) là port loại RESET hay là input điều khiển. Trích: *"\| K6 \| \`phy_core_rst\` polarity and synchronicity;"* | Coi `phy_core_rst` là port loại RESET: port wrapper `<dir>_<ip>_core_rst_n` active-low, inverter đặt trong `m_ftel_dphy_rx_wrap`; logic bên trong không đổi. Hỏi team CSI cùng lúc với K6 | CSI team |
| F-005 | 588 | Thiếu | Appendix A truy vết Q1–Q9 và C2–C16 nhưng thiếu C1 (baseline của HAS-CSI: CSI-2 v1.3 + D-PHY v1.2), dù §1.4 Baselines có hiện thực nó. Trích: *"IDs refer to \`DPHY_RX_RESEARCH_PLAN.md\` §2.1 (Q) and §2.4 (C)."* | Thêm dòng "C1 Baseline CSI-2 v1.3 + D-PHY v1.2 \| §1.4 Baselines" vào Appendix A | Nội bộ |

### 3.2 Từ lần trích độc lập A6

Lần trích độc lập ghi 19 finding. Tôi đã đối chiếu từng finding với dòng spec được trích; A6/F-004 còn được kiểm thêm với D-PHY v1.1 Table 14. Kết quả:

- Hai finding trùng với P1: A6/F-017 = F-002 và A6/F-018 = F-003. Hai lần trích độc lập cùng thấy, nên độ tin cậy của hai finding này tăng.
- Hai finding (A6/F-001, A6/F-002) là về tool chứ không phải về spec; xem D5 ở §4.
- Còn lại 15 finding mới, liệt kê ở bảng dưới.

Cột "Mức":

- **Cao:** ảnh hưởng hành vi RTL hoặc khả năng tương thích với Tx.
- **Thấp:** sửa câu chữ, hoặc chỉ cần làm rõ.

| ID | Dòng | Vấn đề | Kiểm chứng | Đề xuất (tóm tắt) | Mức | Chủ |
|---|---|---|---|---|---|---|
| A6/F-004 | 232 | Bộ đếm `PARA_SYNC_SEARCH_BYTES` = 16 byte bắt đầu từ khi THS-SETTLE hết. Nhưng D-PHY chỉ cho giá trị min của THS-PREPARE + THS-ZERO, không có max. Ở 1500 Mb/s, 16 byte ≈ 85 ns, nên một Tx hợp lệ phát HS-0 dài hơn sẽ làm Rx báo `errsotsynchs_x` sai | ✅ Table 14 chỉ có cột min (145 ns + 10·UI) | Đếm từ byte khác 0 đầu tiên (hết HS-0), không đếm từ lúc THS-SETTLE hết; hỏi Tx THS-ZERO max (S5). Có liên quan tới F-001 của P1 | Cao | Nội bộ + Tx |
| A6/F-012 | 334, 344 | Luật chung "mọi trạng thái về DL_STOP khi gặp LP-11" mâu thuẫn với các dòng riêng: DL_LP_RQST ghi LP-11 → DL_ERR; DL_ESC_RQST ghi "other → DL_ERR", tức là gồm cả LP-11. Chưa rõ luật nào ưu tiên, trong khi điều này quyết định có phát `errcontrol_x` hay không | ✅ đọc dòng 334, 336, 344 | Dòng riêng ưu tiên: đi qua DL_ERR (phát `errcontrol_x`) rồi về DL_STOP | Cao | Nội bộ |
| A6/F-008 | 243 | `esc_timeout_cyc` không nói áp dụng cho những trạng thái nào. ULPS có thể kéo dài vô hạn và Mark-1 kéo dài ≥ 1 ms, nên watchdog chạy trong DL_ULPS sẽ ngắt ULPS hợp lệ | ✅ dòng 243, 386; FSM không có lối ra timeout của escape | Chỉ áp dụng cho các trạng thái từ DL_LP_RQST đến DL_ESC_CMD | Cao | Nội bộ |
| A6/F-015 | 386 | Khi watchdog escape hết hạn: FSM sang trạng thái nào, có cờ lỗi hay status không? Chưa định nghĩa | ✅ bảng FSM §4.5 không có | Chuyển sang trạng thái chờ LP-11, không phát lỗi PPI, bật một cờ sticky ở Block No. 8 | Cao | Nội bộ |
| A6/F-010 | 283 | Đảo cực P/N và map lane chỉ áp dụng cho đường HS. Nếu board đảo P/N thì LP-01 và LP-10 cũng bị đảo | ✅ dòng 283–284 | Áp dụng cùng phép đảo cực và map lane cho đường LP trong Block No. 1 | Cao | Nội bộ |
| A6/F-011 | 303 | CL_HS_RQST chỉ có lối ra cho LP-00 và LP-11; phản ứng khi gặp LP-10 chưa định nghĩa. Clock lane cũng không có trạng thái lỗi | ✅ dòng 303 | Coi là yêu cầu bị hủy: chờ LP-11 rồi về CL_STOP, bật cờ status | Cao | Nội bộ |
| A6/F-005 | 239 | `hs_settle_cyc` = 20 chỉ đúng cho 1500 Mb/s. Ở 80 Mb/s, cửa sổ THS-SETTLE là 160–270 ns, mà 20 × 5 ns + ~20 ns = 120 ns nằm ngoài cửa sổ. Công thức có ở Appendix B, nhưng spec không bắt buộc software lập trình lại khi đổi tốc độ | ✅ số học đúng; Appendix B dòng 617 có công thức | Công bố bảng giá trị theo tốc độ; software phải lập trình trước khi enable lane | Cao | CSI team (K3) |
| A6/F-014 | 374–378 | Ghi chú thiết kế về việc qualify sync ở tốc độ thấp ("run of zeros") còn ghi "micro-architecture to confirm"; chưa định nghĩa độ dài chuỗi zero | ✅ dòng 377–378 | Chỉ chấp nhận leader sau ít nhất 1 byte toàn 0; thêm test 80 Mb/s với THS-ZERO min | Cao | Nội bộ |
| A6/F-016 | 392 | ADR-004 (thuật toán deskew) bị hoãn tới R2 nhưng không có trong bảng Open Items §9 | ✅ §9 chỉ có K1–K6, ADR-001, S4, S5, T1 | Thêm ADR-004 vào §9 | Thấp | Nội bộ |
| A6/F-003 | 230 | `PARA_LP_FILTER_CYC` = 2 là giả định; spec không nêu độ rộng glitch LP tối đa mà AFE có thể để lọt | ✅ dòng 230 (có ⚠️) | Hỏi AFE về độ rộng glitch tối đa (A5 ở §4) | Thấp | AFE team |
| A6/F-007 | 242 | Timeout HS RX 2^18 được tính từ dòng 5802 byte; giá trị đúng phụ thuộc độ dài burst lớn nhất theo sensor mode của controller | ✅ dòng 242 | Giữ default; CSI xác nhận độ dài burst tối đa mỗi lane | Thấp | CSI team |
| A6/F-006 | 240 | Chưa nói rõ `clk_settle_cyc` bắt đầu đếm từ đâu và trừ độ trễ nào | ⚠️ một phần đã có câu trả lời: bảng FSM (dòng 305) cho thấy bộ đếm chạy trong CL_HS_TERM | Ghi rõ: đếm từ lúc vào CL_HS_TERM | Thấp | Nội bộ |
| A6/F-009 | 261 | Tên tín hiệu lệch nhau: `lp_dp/dn_x`, `hs_en_x`, `term_en_x` ở §2, §4 so với `afe_*` ở §5.2 | ✅ dòng 261 và 459–468 | Dùng tên `afe_*` ở biên IP; tên không prefix là tên nội bộ | Thấp | Nội bộ |
| A6/F-013 | 361, 580 | Ký hiệu 🌐 không có trong bảng Conventions | ✅ dòng 17–22 | Thêm 🌐 vào Conventions (nguồn thứ cấp, chưa kiểm với `ref/spec`) | Thấp | Nội bộ |
| A6/F-019 | 197 vs 430 | Bảng PPI ghi nguồn của `init_done` là No.6, nhưng sơ đồ §2 vẽ `init_done` đi ra từ hộp Block No. 8 | ✅ dòng 196–197 | Sửa sơ đồ: `init_done` đi ra từ No.6 | Thấp | Nội bộ |

Nhận xét:

- **Hai lần trích bỏ sót finding của nhau khá nhiều.**
  - P1 ghi 5 finding; A6 ghi 17 finding về spec.
  - Chỉ 2 finding trùng hẳn; 1 finding liên quan (F-001 của P1 và A6/F-004).
  - Như vậy một lần trích đơn lẻ **không đủ để dò chỗ mơ hồ**. Đề xuất D6 ở §4 xử lý điểm này.
- **Nhóm "Cao" gồm 8 finding.** Tất cả đều ảnh hưởng FSM hoặc datapath, nên cần chốt trong spec v0.4, trước Stage C:
  - F-002 (P1);
  - A6/F-004, F-012, F-008, F-015, F-010, F-011, F-014.
- **F-002 (P1) = A6/F-017** là finding có ảnh hưởng thiết kế lớn nhất: nó quyết định cấu trúc tầng output của Block No. 7 và thêm một đường CDC.
- **F-003 và F-005 (P1)** chỉ là sửa câu chữ trong spec.

## 4. Đề xuất bổ sung danh sách sync-up (d)

⚠️ Chỉ là đề xuất. Theo kế hoạch A7, research plan chỉ được sửa sau khi bạn xác nhận trong chat.

| # | Đề xuất | Bằng chứng | Chỗ sẽ sửa khi được duyệt |
|---|---|---|---|
| D1 | **Mở rộng K6**, thêm câu hỏi: "`phy_core_rst` là port loại RESET theo Wrapper Guideline (active-low `_n` ở wrapper) hay là input điều khiển? Cực tính CSR phía controller là gì?" | F-004. K6 hiện chỉ hỏi cực tính và tính đồng bộ, chưa gắn với quy ước wrapper của FX1 | Research plan §5.2 dòng K6 |
| D2 | **Thêm §5.3 "Với team AFE"**, gồm 5 câu hỏi rút từ ADR-001, ADR-004 và A6/F-003 (bảng dưới) | 7 REQ có chủ là AFE team, nhưng research plan §5 mới có danh sách cho Tx (S) và CSI (K). Spec §9 đã ghi chủ của ADR-001 là "AFE team", nhưng chưa có kênh câu hỏi tương ứng | Research plan §5.3 (mới), §6 P1 thêm "và với team AFE (A1–A5)" |
| D3 | **Đưa các finding nội bộ ở §3.1 và §3.2 vào spec v0.4** dưới dạng làm rõ hoặc sửa câu chữ. Ưu tiên 8 finding mức "Cao". Không thêm vào K/S vì đây là quyết định nội bộ | §3 | `doc/spec.md` (cần duyệt riêng vì là thay đổi kỹ thuật) |
| D4 | **Hỏi thêm Tx và CSI.** (i) Dòng S5 trong §9 của spec thêm "THS-ZERO max", vì giá trị này quyết định cửa sổ tìm sync. Research plan S5 đã hỏi THS-ZERO, chỉ riêng spec chưa ghi. (ii) Thêm **K8**: "Độ dài burst HS tối đa mỗi lane, cho mọi sensor mode và tổ hợp lane/tốc độ", vì nó quyết định `hs_rx_timeout_cyc` | A6/F-004, A6/F-007 | Spec §9 dòng S5; research plan §5.2 thêm K8 |
| D5 | **Bổ sung answer key.** Thêm chữ ký header của bảng §1.3 (Path) và §1.4 (Release) vào `spec_inventory.py`, và cập nhật `EXPECTED` trong cùng commit. Thao tác này đổi answer key đã đăng ký trước, nên chỉ làm khi bạn đồng ý, và ghi lý do vào lịch sử của script | A6/F-001, A6/F-002: hai bảng này có yêu cầu `[CSI]` nhưng hiện chỉ được chấm như văn xuôi | `hw/utils/req_flow/spec_inventory.py` |
| D6 | **Đổi quy trình review:** mỗi lần review spec chạy **hai lần trích độc lập**, rồi hợp nhất finding (loại trùng). Việc này tách khỏi việc sinh REQ chính thức | §3.2: hai lần trích chỉ trùng 2–3 finding; mỗi lần bỏ sót phần lớn finding của lần kia | `dphy_spec_parse.md`, `dphy_autoflow.md` (P1 ở chế độ review) |

Nội dung đề xuất cho D2:

| ID | Câu hỏi cho team AFE | Default hiện tại trong spec | REQ liên quan |
|---|---|---|---|
| A1 | Ranh giới AFE / digital: AFE có giao 8-bit word đã deserialize (chưa align) cho mỗi lane, trên một byte clock chung không (option B)? | Option B (§5.2) | REQ-003, REQ-141, REQ-152, REQ-177 |
| A2 | AFE có cung cấp bộ phát hiện clock activity (`afe_cl_clk_active`) để đạt TCLK-MISS ≤ 60 ns ở 80 Mb/s không? Nếu không, có chấp nhận nới yêu cầu này ở tốc độ thấp không? | Có detector trong AFE ⚠️ (§4.4 note, §5.2) | REQ-065 |
| A3 | Sau khi phần digital đã dùng khoảng 20 ns độ trễ, AFE còn đáp ứng được phần ngân sách còn lại của TD-TERM-EN (≤ 35 ns + 4 UI) và TCLK-TERM-EN (≤ 38 ns) không? Nếu không, việc chuyển termination sẽ nằm trong AFE | Digital phát termination enable ngay khi phát hiện LP-00 (§4.3) | REQ-053 |
| A4 | Delay line cho deskew (R2): số tap, độ phân giải mỗi tap, dải chỉnh, và giao diện điều khiển | Chưa xác định (`PARA_DLY_TAP_WIDTH`, ADR-004) | REQ-032, REQ-101, REQ-102 |
| A5 | Độ rộng glitch tối đa mà LP-RX của AFE có thể để lọt vào phần digital là bao nhiêu? Giá trị này quyết định `PARA_LP_FILTER_CYC`, và bộ lọc này ăn vào ngân sách TD-TERM-EN | 2 chu kỳ `core_clk` ⚠️ (§3 #7) | A6/F-003 |

## 5. Độ ổn định của phép trích (A6)

### 5.1 Cách đo

**Lần trích độc lập (A6).**
- Chạy trong subagent riêng.
- Chỉ được đọc: `dphy_spec_parse.md`, `spec.md`, và các script/schema trong `hw/utils/req_flow/`.
- Bị cấm đọc: `req/_work/P1/`, `req/structured_spec.json`, và hai file plan.
- ✅ Transcript cho thấy agent không mở file nào trong vùng cấm, và `git status` không đổi.
- ⚠️ Subagent vẫn kế thừa `CLAUDE.md` và auto-memory của dự án. Các file này có mô tả dự án, nhưng không chứa artifact P1.

**Metric (`compare_req.py`, đăng ký ngày 2026-09-26, trước khi xem kết quả A6).**
- Neo = 108 dòng bảng được chấm.
- Với mỗi neo, lấy REQ đầu tiên của mỗi lần trích, rồi so 4 trường: `category`, `block`, `spec_status`, `needs_human_decision`.
- Ngưỡng đạt: 90%.

### 5.2 Kết quả

```text
anchors: 108   agreeing: 86   agreement: 79.6%   threshold: 90%
per field: category 107/108, block 98/108, spec_status 97/108, needs_human_decision 97/108
REQs: A=190  B=218   findings: A=5  B=19
prose source lines: A=82  B=84  Jaccard=0.58
RESULT: FAIL
```

**A6 FAIL: 79,6% < 90%.** Metric và ngưỡng được giữ nguyên như đã đăng ký, không chỉnh sau khi xem kết quả.

Những gì hai lần trích **giống nhau**:

| Mặt | P1 | A6 |
|---|---|---|
| Trích dẫn nguyên văn | 195/195 | 237/237 |
| Độ phủ inventory | 100% | 100% |
| Lỗi validator | 0 | 0 |
| Số REQ `needs_human_decision` | 37 | 37 (khác thành phần) |

Tức là lớp kiểm được bằng máy ổn định; phần lệch nằm hoàn toàn ở các trường phán đoán.

### 5.3 Nguyên nhân gốc của 22 neo lệch

Cả 22 neo lệch đều quy được về 4 luật mà prompt chưa định nghĩa. Không có neo nào lệch do trích sai hay do bịa nội dung.

| # | Luật còn thiếu trong `dphy_spec_parse.md` | Neo lệch | P1 đọc là | A6 đọc là |
|---|---|---|---|---|
| RC1 | Chữ OPEN nằm trên **heading hoặc caption**, hoặc dòng chỉ **dẫn ID của §9** mà không có chữ OPEN, thì có làm các dòng bên dưới thành `open` không? | 10 neo: 8 dòng AFE ở §5.2 (heading "(proposed, OPEN ADR-001)"), `errsyncesc_x` (K2), TCLK-MISS (ADR-001) | Chỉ tính tag trên chính dòng đó; 8 dòng AFE là `assumed` | Kế thừa tag; 8 dòng AFE là `open` + `needs_human_decision` |
| RC2 | Giá trị "To be determined" mà không có chữ OPEN | 1 neo: `PARA_DLY_TAP_WIDTH` | `open` | `design`, ambiguity 0.7 |
| RC3 | Gán `block` cho **port input ở biên IP** (cột Source ghi "—") và cho dòng **liên block** (CDC, K6, TWAKEUP): chọn `top`, `all` hay block tiêu thụ? Schema có sẵn giá trị `top` nhưng prompt không định nghĩa khi nào dùng | 10 neo | `all` hoặc block tiêu thụ | `top` hoặc block khác |
| RC4 | `category` của dòng bảng clock có chữ OPEN | 1 neo: configuration clock | `decision` | `clocking` |

Đánh giá ⚠️: về RC1, cách đọc của A6 sát nghĩa hơn với §5.2, vì heading nói rõ cả giao diện AFE còn OPEN. Tuy vậy, ảnh hưởng thực tế lên P1 nhỏ: bảy REQ ở §2.3 vẫn giữ ADR-001 ở dạng `needs_human_decision`, nên không mất quyết định nào.

### 5.4 Đề xuất xử lý (chờ bạn chọn)

**Phương án 1 (khuyến nghị): biến 4 luật trên thành luật tất định, rồi đo lại.** Theo nguyên tắc P2 của kế hoạch: cái gì script kiểm được thì script kiểm.

1. **Sửa `spec_inventory.py`:** tính phạm vi của heading và caption. Dòng nằm dưới một heading hoặc caption có chữ OPEN được đưa vào `open_lines`; dòng có "To be determined" cũng vậy.
2. **Sửa `validate_req.py`, thêm 2 luật:**
   - Với các dòng bảng, `category` được suy ra từ loại bảng.
   - Block của dòng PPI lấy theo cột Source. Input không có Source → `top`. Dòng liên block → `all`.
3. **Ghi 4 luật vào `dphy_spec_parse.md`.**
4. **Sinh lại chunk P1** bằng prompt mới (không sửa JSON bằng tay), rồi **chạy lại A6 clean-room**:
   - mất khoảng 20 phút và khoảng 230k token;
   - so lại bằng cùng metric, cùng ngưỡng 90%.

Lưu ý: bước 1 làm tập dòng OPEN thay đổi, nhưng các số trong `EXPECTED` thì không đổi (các số đó đếm dòng bảng, không đếm tag).

**Phương án 2: dừng ở mức "đã giải thích".** Điều kiện Exit A cho phép "A6 ≥ 90% hoặc đã giải thích chỗ khác", và §5.3 đã giải thích đủ 22/22 neo lệch. Khi đó 4 luật chỉ được ghi lại, để sửa trước Stage C. Rủi ro: đến Stage C, CF-OPEN chặn sinh RTL theo `block` và `spec_status`. Nếu hai trường này chưa ổn định thì việc chặn cũng không ổn định.

## 6. Giới hạn của review này

- ✅ Validator chứng minh ba điều:
  - mỗi REQ đều trích đúng câu có thật trong spec;
  - mỗi dòng bảng đều sinh ra ít nhất một REQ;
  - các cờ tuân luật tag.
- ⚠️ Validator **không** chứng minh được rằng diễn giải của REQ là đúng. Các trường `category`, `block`, `spec_status` và nội dung `text` là phán đoán của LLM. Bước A6 đo độ ổn định của phán đoán này được 79,6% ở 4 trường (§5), dưới ngưỡng 90%.
- ⚠️ Độ phủ chỉ được chấm cho **dòng bảng** và các Q/C-ID. Câu văn xuôi không có answer key, nên REQ rút từ văn xuôi chỉ được kiểm ở mức trích dẫn.
- 🔍 Artifact gắn với sha256 của spec v0.3. Bất kỳ sửa đổi nào của spec (kể cả D3) đều làm validator báo CF-SPEC, và P1 phải chạy lại.

**Độ tin cậy:**
- **CAO** cho §1: số liệu lấy trực tiếp từ output của tool.
- **CAO** cho việc nhóm theo chủ ở §2: tính bằng script từ `open_item_ref`.
- **TRUNG BÌNH** cho các default đề xuất ở §3 và §4: dựa trên đọc spec, chưa có ý kiến của các team.
- **CAO** cho kết quả và phân loại nguyên nhân ở §5: số liệu lấy từ `compare_req.py`, và cả 22/22 neo lệch đã được đối chiếu từng cái.
- **THẤP** cho việc cho rằng Phương án 1 sẽ đưa kết quả vượt 90%: chưa đo, phải chạy lại mới biết.

## 7. Trạng thái xử lý (2026-09-26)

D1–D6 đã được duyệt và đã áp dụng. Review này vẫn là review của **spec v0.3**.

| # | Đã làm | File |
|---|---|---|
| D1 | Mở rộng K6: phân loại port theo Wrapper Guideline, cực tính bit CSR | Research plan §5.2; spec §9 dòng K6 |
| D2 | Thêm §5.3 "Với team AFE" (A1–A5); §6 P1 thêm team AFE | Research plan |
| D3 | Spec **v0.4**. Làm rõ: P1 F-001…F-003, F-005; A6/F-004, F-005, F-006, F-008…F-016, F-019. Sơ đồ §2 vẽ lại mũi tên `init_done`; thêm 1 dòng CDC (gate output PPI); §8 thêm kịch bản test | `doc/spec.md` |
| D4 | S5 thêm THS-ZERO max; thêm K8 vào spec §9 và research plan §5.2 | Spec §9; research plan |
| D5 | Thêm hai loại bảng `path` (5 dòng) và `release` (2 dòng). `EXPECTED` tách theo revision; số của v0.4 được ghi trước khi sửa spec | `hw/utils/req_flow/spec_inventory.py` |
| D6 | Thêm Bước 4b: lượt dò finding độc lập, chạy nền song song với lượt trích chính, hợp nhất trước khi assemble | `.claude/commands/dphy_spec_parse.md`, `dphy_autoflow.md` |

Kiểm chứng:

- ✅ `spec_inventory.py --selftest`: PASS trên v0.2, v0.3 và v0.4. Các số của v0.4 là: cdc 6, open 12, c_ids 16, path 5, release 2.
- ✅ `flow_check.py --phase P1 --no-state` trên artifact hiện có cho **exit 2, CF-SPEC**: artifact được dựng trên v0.3, còn spec đã là v0.4. Flow dừng đúng như thiết kế.
- ⚠️ `req/structured_spec.json` và các con số ở §1–§2 là của v0.3. Chúng phải được đồng bộ lại với v0.4 trước khi dùng tiếp. Phân loại 195 trích dẫn (190 REQ + 5 finding) so với v0.4:

  | Trạng thái | Số lượng |
  |---|---|
  | Vẫn đúng dòng | 13 |
  | Còn nguyên văn nhưng dịch dòng | 164 |
  | Câu gốc đã bị sửa | 18 (REQ-029, 031, 033, 034, 036, 037, 041, 057, 086, 109, 162, 166, 176, 177, 179, 183; F-001, F-003) |

### 7.1 Phương án 1 cho A6 (đã duyệt, đã làm)

4 luật RC1–RC4 ở §5.3 nay do script tính (`hw/utils/req_flow/derive_rules.py`). `assemble_req.py` áp các luật này; validator kiểm lại bằng luật `DERIVE`, map sang CF-SCHEMA. Hai lần trích v0.3 **không phải sinh lại**: chúng được assemble lại từ chunk có sẵn, rồi chấm bằng cùng metric và cùng ngưỡng 90%.

| Tập neo | Trước | Sau | Chỗ lệch còn lại |
|---|---|---|---|
| 108 neo của lần đo đầu | 79,6% | **99,1%** (107/108) | `errsyncesc_x`: `design` vs `contract`. Nguyên nhân là spec thiếu dẫn chiếu K2; v0.4 đã bổ sung |
| 115 neo (thêm bảng Path, Release theo D5) | — | 94,8% (109/115) | Thêm 5 dòng Path mà P1 chưa có REQ, đã bổ sung khi đồng bộ v0.4 |

⚠️ Cách đọc đúng cho con số này:
- Ở các neo, `category`, `block` và phần `open` của `spec_status` giờ **khớp nhau vì luật tính ra**, không phải vì LLM ổn định hơn.
- Luật được thiết kế sau khi đã thấy 22 chỗ lệch.
- Phần metric còn đo được phán đoán của LLM là: neo có REQ hay không, và `spec_status` ngoài `open` (`assumed`/`contract`/`verified`/`design`).
- Độ ổn định của REQ văn xuôi (Jaccard 0,58) và của finding chưa có metric riêng.

### 7.2 Đồng bộ P1 với spec v0.4 (chế độ tăng dần)

| Bước | Kết quả |
|---|---|
| `rebase_req.py` | Giữ 166/190 REQ với số dòng mới, không cần sinh lại; 24 REQ lỗi thời; 23 vùng spec mới hoặc đã đổi |
| Finding cũ | Cả 5 finding (F-001…F-005) được bỏ vì vấn đề đã sửa trong v0.4 (F-005: C1 đã có trong Appendix A) |
| Sửa tay chunk | Thêm `C1` vào `source_ids` của REQ Baselines, vì Appendix A v0.4 ánh xạ C1 → §1.4 |
| Chunk bổ sung | 42 REQ: 24 REQ sinh lại, nội dung mới, 5 dòng Path. Thêm 1 finding mới về v0.4: giữ `errcontrol_x` bao lâu khi lỗi do chính LP-11 gây ra (C13), chủ là CSI team |
| `validate_req.py` | 208 REQ · 1 finding · trích dẫn 209/209 · độ phủ 100% ở 15 nhóm · 0 lỗi · 0 cảnh báo |
| `flow_check.py` | review: 0 xung đột, `flow_state.json` đã cập nhật · gate: dừng với 45 CF-OPEN · test âm **7/7 PASS** (thêm test DERIVE) |

`needs_human_decision` tăng từ 37 lên 45, do:
- K8 và ADR-004 là mục mở mới;
- 8 dòng AFE nay thuộc phạm vi OPEN của heading §5.2;
- 5 dòng Path có tag OPEN.

Các con số ở §1–§2 là của v0.3 và được giữ nguyên làm hồ sơ review.

### 7.3 Đồng bộ P1 với spec v0.5 (hình vẽ, 2026-09-29)

Spec v0.5 thay khung ASCII ở §2 bằng hình vẽ (Figure 2-1…2-4), thêm §2.1 (Universal Lane Module của
D-PHY và nơi hiện thực từng chức năng) và bổ sung việc đồng bộ `afe_cl_clk_active`. Chỗ thiếu này lộ
ra khi vẽ Figure 2-4: spec chưa nói block nào đồng bộ input bất đồng bộ đó.

| Bước | Kết quả |
|---|---|
| `spec_inventory.py` | Đếm trước cho v0.5, ghi trước khi sửa spec: cdc 6 → 7. Bảng ánh xạ ULM của §2.1 đăng ký là bảng từ vựng (`ulm`), không chấm coverage. Selftest PASS |
| `rebase_req.py` | Giữ 208/208 REQ và 1/1 finding với số dòng mới; 0 mục lỗi thời; 6 vùng mới hoặc đã đổi |
| Chunk bổ sung `20_v05_delta.json` | 2 REQ: dòng CDC mới của §4.1 (OPEN theo ADR-001) và bullet mới của §4.3 (⚠️). §2.1 và §2.2 không sinh REQ: đó là mô tả tham chiếu D-PHY, định nghĩa nhãn của hình và một bảng từ vựng; các câu có tính quy định đã có REQ ở §1.4, §4.4, §4.5. Dòng version và dòng revision không phải yêu cầu |
| So nội dung | 208 REQ cũ giống hệt v0.4, trừ `req_id` và `source_line` |
| `validate_req.py` | 210 REQ · 1 finding · trích dẫn 211/211 · độ phủ 100% ở 15 nhóm (cdc 7/7) · 0 lỗi · 0 cảnh báo |
| `flow_check.py` | review: 0 xung đột, `flow_state.json` đã cập nhật · test âm **7/7 PASS** |

`needs_human_decision` tăng từ 45 lên 46 (REQ mới phụ thuộc ADR-001). File hỏi team AFE cập nhật
theo: ADR-001 chặn 17 REQ, và A2 có thêm câu về glitch của `afe_cl_clk_active`.

`req_id` được gán theo thứ tự dòng trong spec, nên hai REQ mới làm 161 ID phía sau dịch +1 hoặc +2
(ví dụ REQ-048 cũ nay là REQ-049). Các ID nhắc trong §1–§7.2 là ID tại thời điểm viết mục đó.

### 7.4 Đồng bộ P1 với spec v0.6 (hình chi tiết từng block, 2026-09-29)

Spec v0.6 thêm Figure 4-1…4-13, vẽ từng block tới phần tử chuẩn. Theo luật "text first" của
`doc/figures/README.md`, chỗ nào hình cần thì text được viết rõ ra trước. Khi vẽ cũng lộ ra các vấn đề
thiết kế ở tốc độ thấp; chúng được ghi thành design note ⚠️ ở §4.5 và §4.6, và ADR-006 được mở lại
cho dải dưới ~270 Mb/s.

| Bước | Kết quả |
|---|---|
| `spec_inventory.py` | Số đếm cho v0.6 lấy từ danh sách thay đổi: runtime 5 → 6 (`eot_skip_bytes`), cdc 7 → 8 (crossing của status), fsm_cl 10 → 11 (CL_WAIT), open 12 → 13 (ADR-006). Lần này số đếm được đăng ký **sau** khi sửa spec (các sửa đổi phát sinh trong lúc vẽ) nhưng **trước** khi chạy inventory trên v0.6. Selftest PASS 15/15 |
| `rebase_req.py` | Giữ 191/210 REQ với số dòng mới; 19 REQ và 1 finding lỗi thời vì text của chúng đã đổi; 29 vùng mới hoặc đã đổi |
| Chunk bổ sung `21_v06_delta.json` | 73 REQ: 19 chủ đề cũ viết lại theo text mới, 54 REQ mới. Câu trích được script cắt từ spec giữa hai mốc và kiểm theo đúng cửa sổ của validator. Finding F-001 giữ nguyên nội dung vì câu hỏi về `errcontrol_x` vẫn chưa có câu trả lời; nó chỉ dời sang dòng mới |
| Schema | `parameters_affected` chấp nhận thêm `*_bytes`, vì trường run-time mới `eot_skip_bytes` đếm theo byte chứ không theo chu kỳ `core_clk`. Validator vẫn kiểm tên đó có trong bảng của spec |
| `validate_req.py` | 264 REQ · 1 finding · trích dẫn 265/265 · độ phủ 100% ở 15 nhóm (runtime 6/6, cdc 8/8, fsm_cl 11/11, open 13/13, c_ids 16/16) · 0 lỗi · 0 cảnh báo |
| `flow_check.py` | review: 0 xung đột · test âm **7/7 PASS** |

`needs_human_decision` tăng từ 46 lên 54: ADR-006 +5, K2 +1 (tie-off LPDT ở §4.9), K6 +1
(`init_done` ở §4.7), T1 +1 (thứ tự bit trigger ở §4.5). Trong 191 REQ giữ nguyên nội dung, 149 REQ
bị đánh lại ID theo thứ tự dòng.

Lượt dò finding độc lập (Bước 4b của `/dphy_spec_parse`) không chạy cho lần đồng bộ này. Các vấn đề
tìm được khi vẽ đã nằm trong spec, dưới dạng design note ⚠️ và mục ADR-006 của §9.

### 7.5 Đồng bộ lại sau quyết định ADR-006 (vẫn là v0.6, 2026-09-29)

Người thiết kế chọn cho ADR-006 phương án lane vẫn đợi EoT done rồi mới về Stop. Phương án không đợi
được giữ trong §4.5 dưới dạng ghi chú "faster option". Khi viết lại design note, lộ thêm một điểm:
EoT done rời Block No. 4 trước khi delay line xả hết. Vì vậy `stopstate_x` có thể lên trước byte cuối,
sớm hơn khoảng mà HAS-CSI Figure 4-1 để ngỏ (từ byte cuối trở đi). Điểm này có ở cả hai phương án.
Nó được ghi là OPEN ADR-006 và hỏi team CSI, không tự quyết. Ràng buộc THS-EXIT + TLPX dưới khoảng
240 Mb/s được hỏi phía Tx ở S5. K3 được bổ sung trường `eot_skip_bytes` còn thiếu.

| Bước | Kết quả |
|---|---|
| `spec_inventory.py` | Không đổi số dòng của bảng nào, nên EXPECTED v0.6 giữ nguyên; điều này được dự đoán trước khi chạy. Selftest PASS 15/15 |
| `rebase_req.py` | Giữ 261/264 REQ; 3 REQ lỗi thời: design note §4.5, đoạn ADR-006 ở §7, dòng ADR-006 ở §9 |
| Chunk bổ sung `22_v06_adr006_delta.json` | 7 REQ viết theo text mới; câu trích cắt bằng script như ở §7.4 |
| `validate_req.py` | 268 REQ · 1 finding · trích dẫn 269/269 · độ phủ 100% ở 15 nhóm · 0 lỗi · 0 cảnh báo |
| `flow_check.py` | review: 0 xung đột · test âm **7/7 PASS** |

`needs_human_decision` tăng từ 54 lên 56 (ADR-006: 5 → 7). 134 REQ bị đánh lại ID theo thứ tự dòng.

Hạn chế đã biết của `rebase_req.py`: REQ được giữ lại vẫn mang `source_section` cũ khi heading đổi
(REQ của đoạn đầu ADR-006 còn heading của v0.5). Validator không chấm trường này.

### 7.6 Đồng bộ P1 với spec v0.7 (định dạng HAS, 2026-09-29)

Spec v0.7 chỉ đổi cách trình bày, để build được bản Word theo định dạng HAS-CSI (`doc/md2docx.py`):
- ba sketch ASCII của §1 thành Figure 1-1…1-3;
- mọi bảng có caption đánh số;
- câu quy ước tên tín hiệu chuyển vào §1;
- thêm Appendix C Acronyms.

Không thay đổi kỹ thuật.

| Bước | Kết quả |
|---|---|
| `spec_inventory.py` | EXPECTED v0.7 đăng ký **trước** khi sửa spec, bằng số của v0.6 (không đổi số dòng của bảng nào). Selftest PASS 15/15. Số dòng phụ thuộc open item tăng 120 → 127: các caption và dòng trống mới nằm trong vùng OPEN (§5.2, ADR-001, ADR-005) và dòng "OPEN" của bảng Acronyms; không dòng nào là nguồn của REQ |
| `rebase_req.py` | Giữ 266/268 REQ; 2 REQ đổi chỗ (câu quy ước tên tín hiệu, caption "Release plan") được chuyển sang dòng mới trong chunk `23_v07_delta.json`, nội dung giữ nguyên |
| `validate_req.py` | 268 REQ · 1 finding · trích dẫn 269/269 · độ phủ 100% ở 15 nhóm · 0 lỗi · 0 cảnh báo |
| `flow_check.py` | review: 0 xung đột; `needs_human_decision` giữ 56 |

### 7.7 Đồng bộ P1 với spec v0.8 (waveform, 2026-09-30)

Spec v0.8 thêm 9 waveform: PPI ở §5.1 (Figure 5-1…5-8) và SoT/EoT ở giao diện AFE ở §5.2 (Figure 5-9).
Khi dựng timeline, lộ ra 5 chỗ spec chưa đúng hoặc chưa đủ. Bốn chỗ nội bộ được sửa ngay trong text,
đánh ⚠️:
- CL_HS_TERM phải đợi thêm clock active. Nếu không, FSM vào CL_HS_CLK trong TCLK-ZERO và thoát ngay vì
  "clock lost"; `cl_rxclkactivehs` cũng lên trước khi `rxbyteclkhs` chạy, trong khi HAS-CSI coi nó là
  dấu hiệu duy nhất cho biết byte clock đang chạy.
- Hết cửa sổ tìm sync thì bộ đếm dừng và comparator bị khóa, để chỉ có một xung `errsotsynchs_x`.
- Phát hiện deskew thì xóa luôn thanh ghi lock, để không entry nào sau đó mang cờ valid.
- Mô tả thời điểm `rxskewcalhs_x` ở PPI: rơi sau `rxactivehs_x` khoảng `eot_skip_bytes` byte clock.

Chỗ thứ năm cần quyết định nên thành mục mở mới **ADR-007**, kèm ma trận ba phương án (Table 7-4). Quy
tắc "leader chỉ được nhận sau một word toàn 0" có hai lỗ hổng:
- Dưới khoảng 170 Mb/s, nếu Tx dùng THS-PREPARE + THS-ZERO tối thiểu, leader có thể bị từ chối.
- Ở tốc độ cao, word rác trong THS-PREPARE có thể khởi động cửa sổ tìm sync.

Ngoài ra, spec ghi thêm rằng IP cần continuous clock (delay line EoT chỉ xả khi byte clock chạy). Điều
này khớp với HAS-CSI C5.

| Bước | Kết quả |
|---|---|
| `spec_inventory.py` | EXPECTED v0.8 đăng ký **trước** khi sửa spec: `open` 13 → 14 (ADR-007), các nhóm khác giữ nguyên. Selftest PASS 15/15. Số dòng phụ thuộc open item tăng 127 → 174: mục ADR-007 (heading có OPEN), phần timing mới của §5.2 (nằm dưới heading OPEN ADR-001) và các dòng dẫn ADR-006/ADR-007/K6 |
| `rebase_req.py` | Giữ 259/268 REQ; 9 REQ lỗi thời vì text đổi (§1.4 clock lane, dòng CL_HS_TERM, settle counter, "clock activity lost", hai REQ ADR-006 ở §4.5, không tìm thấy sync, hủy lock khi gặp deskew, kịch bản SoT ở §8) |
| Chunk bổ sung `24_v08_delta.json` | 28 REQ, gồm 9 REQ viết lại và 19 REQ mới, cùng 1 finding. Câu trích được kiểm nguyên văn bằng script trước khi assemble; luật `derive_rules` không phải ghi đè trường nào của chunk này |
| `validate_req.py` | 287 REQ · 2 finding · trích dẫn 289/289 · độ phủ 100% ở 15 nhóm · 0 lỗi · 0 cảnh báo |
| `flow_check.py` | review: 0 xung đột; `needs_human_decision` 56 → 60 (4 REQ của ADR-007); test âm **7/7 PASS** |

Finding mới (owner: CSI team) là một chỗ HAS-CSI tự mâu thuẫn:
- Table 4-4 (#8) và phần Lane Management đặt `rxsynchs_x` cùng chu kỳ với byte đầu.
- Figure 4-1 lại vẽ xung trước byte đầu một chu kỳ.
- Điều kiện ghi FIFO của HAS-CSI chấp nhận cả hai cách.
- IP này theo Table 4-4.

Không tạo REQ cho các câu chỉ là lý do hoặc nhắc lại yêu cầu đã có, theo quy tắc của `dphy_spec_parse`:
- bằng chứng từ HAS-CSI về cách dùng `stopstate_x`;
- các gạch đầu dòng ở §5.1/§5.2 lặp lại yêu cầu của §4;
- ma trận Table 7-4.

249 REQ cũ bị đánh lại ID theo thứ tự dòng.
