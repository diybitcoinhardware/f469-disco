/**
 * @file       t1_protocol.c
 * @brief      ISO/IEC 7816 T=1 Protocol Implementation
 * @author     Mike Tolkachev <contact@miketolkachev.dev>
 * @copyright  Copyright 2020 Crypto Advance GmbH. All rights reserved.
 */

/// Enables implementation of FIFO functions
#define FIFO_BUF_IMPLEMENT
#include "t1_protocol.h"

/// Default sleep time in milliseconds
#define DEF_SLEEP_TIME_MS               50
/// Maximal timeout in milliseconds, renamed
#define TM_MAX                          T1_MAX_TIMEOUT_MS

/// NAD byte with default values
#define TX_NAD_VALUE                    0x00
/// Bit mask used to obtain block type marker from PCB byte
#define PCB_MARKER_MASK                 0xC0

/// I-block: sequence number, "N(S)" bit in PCB byte
#define IB_NS_BIT                       0x40
/// I-block: more-data bit, "M" in PCB byte
#define IB_M_BIT                        0x20

/// R-block marker in PCB byte: 2 higher bits are 10b
#define RB_MARKER                       0x80
/// R-block: sequence number, "N(R)" bit in PCB byte
#define RB_NS_BIT                       0x10
/// R-block: acknowledgement code
#define RB_ACK_MASK                     0x0F

/// S-block marker in PCB byte, 2 higher bits are 11b
#define SB_MARKER                       0xC0
/// S-block: response bit
#define SB_RESP_BIT                     0x20
/// S-block: command mask
#define SB_CMD_MASK                     0x1F

/// Maximal length of EDC code in bytes
#define MAX_EDC_LEN                     2
/// Maximum overhead of I-block
#define MAX_IBLOCK_OVH                  (prologue_size + MAX_EDC_LEN)
/// Maximum size of I-block
#define MAX_IBLOCK_SIZE                 (T1_MAX_APDU_SIZE + MAX_IBLOCK_OVH)

/// Minimal number of bytes for a valid ATR
#define ATR_MIN_BYTES                   2
/// TS0 byte: direct convention
#define TS_CONVENTION_DIRECT            0x3B
/// TS0 byte: inverse convention
#define TS_CONVENTION_INVERSE           0x3F
/// Bit within T0 or TD bytes indicating that TA is present
#define TA_BIT                          (1)
/// Bit within T0 or TD bytes indicating that TB is present
#define TB_BIT                          (1 << 1)
/// Bit within T0 or TD bytes indicating that TC is present
#define TC_BIT                          (1 << 2)
/// Bit within T0 or TD bytes indicating that TD is present
#define TD_BIT                          (1 << 3)
/// LRC size in bytes
#define LRC_SIZE                        1
/// CRC size in bytes
#define CRC_SIZE                        2

/// Block delivery attempts
#define DELIVERY_ATTEMPTS               10
/// Resynchronization attempts
#define RESYNC_ATTEMPTS                 3

/// Minimum value of IFS (maximum information field size) parameter
#define IFS_MIN                         1
/// Maximum value of IFS (maximum information field size) parameter
#define IFS_MAX                         254

/// Identifier of PPS request and response
#define PPSS                            0xFFU

/// MAximal number of events in a list
#define MAX_EVENTS                      3

/// Transmission protocol or qualification of interface bytes
typedef enum {
  atr_prot_t0 = 0,  ///< T=0 protocol
  atr_prot_t1 = 1,  ///< T=1 protocol
  atr_globals = 15, ///< Global interface bytes
} protocol_id_t;

/// Byte offsets and size of T=1 prologue
enum {
  prologue_nad = 0, ///< NAD byte
  prologue_pcb,     ///< PCB byte
  prologue_len,     ///< LEN byte
  prologue_size     ///< Size of prologue
};

// PPS request/response fields
enum {
  pps_ppss = 0, ///< PPS request/response identifier
  pps_pps0,     ///< PPS0 byte
  pps_pck,      ///< PCK, XOR checksum
  pps_size      ///< Size of PPS request/response
};

// PPS request/response fields
enum {
  usb_pps_ppss = 0, ///< PPS request/response identifier
  usb_pps_pps0,     ///< PPS0 byte
  usb_pps_pps1,     ///< PPS1 byte
  usb_pps_pck,      ///< PCK, XOR checksum
  usb_pps_size      ///< Size of PPS request/response
};

/// One entry in extended configuration data table
typedef struct {
  int32_t min;  ///< Allowed minimal value
  int32_t max;  ///< Allowed maximal value
  int32_t def;  ///< Default value
} ext_config_entry_t;

/// Header of the block stored in FIFO buffer
typedef struct {
  unsigned int size : 9;       ///< Block size in bytes
  unsigned int type : 2;       ///< Block type, one of t1_block_type_t enums
  unsigned int more_data : 1;  ///< More data flag, "M"
  unsigned int seq_number : 1; ///< Sequence number "N(S)" or "N(R)"
} block_hdr_t;

/// One entry in a list of constant (read-only) buffers
typedef struct {
  const uint8_t* buf; ///< Pinter to constant buffer, NULL terminates list
  size_t len;         ///< Number of bytes stored in the buffer
} const_buf_t;

/// Event
typedef struct {
  t1_ev_code_t code; ///< Event code
  const void* prm;   ///< Event parameter depending on event code
} event_t;

/// Event list
typedef struct {
  event_t buf[MAX_EVENTS]; ///< Buffer with events
  size_t len;              ///< Index within buf[]
} event_list_t;

/// Empty event
static const event_t event_none = { .code = t1_ev_none };

/// CRC table
static const uint16_t crc_tbl[256] = {
  0x0000, 0x1189, 0x2312, 0x329B, 0x4624, 0x57AD, 0x6536, 0x74BF,
  0x8C48, 0x9DC1, 0xAF5A, 0xBED3, 0xCA6C, 0xDBE5, 0xE97E, 0xF8F7,
  0x1081, 0x0108, 0x3393, 0x221A, 0x56A5, 0x472C, 0x75B7, 0x643E,
  0x9CC9, 0x8D40, 0xBFDB, 0xAE52, 0xDAED, 0xCB64, 0xF9FF, 0xE876,
  0x2102, 0x308B, 0x0210, 0x1399, 0x6726, 0x76AF, 0x4434, 0x55BD,
  0xAD4A, 0xBCC3, 0x8E58, 0x9FD1, 0xEB6E, 0xFAE7, 0xC87C, 0xD9F5,
  0x3183, 0x200A, 0x1291, 0x0318, 0x77A7, 0x662E, 0x54B5, 0x453C,
  0xBDCB, 0xAC42, 0x9ED9, 0x8F50, 0xFBEF, 0xEA66, 0xD8FD, 0xC974,
  0x4204, 0x538D, 0x6116, 0x709F, 0x0420, 0x15A9, 0x2732, 0x36BB,
  0xCE4C, 0xDFC5, 0xED5E, 0xFCD7, 0x8868, 0x99E1, 0xAB7A, 0xBAF3,
  0x5285, 0x430C, 0x7197, 0x601E, 0x14A1, 0x0528, 0x37B3, 0x263A,
  0xDECD, 0xCF44, 0xFDDF, 0xEC56, 0x98E9, 0x8960, 0xBBFB, 0xAA72,
  0x6306, 0x728F, 0x4014, 0x519D, 0x2522, 0x34AB, 0x0630, 0x17B9,
  0xEF4E, 0xFEC7, 0xCC5C, 0xDDD5, 0xA96A, 0xB8E3, 0x8A78, 0x9BF1,
  0x7387, 0x620E, 0x5095, 0x411C, 0x35A3, 0x242A, 0x16B1, 0x0738,
  0xFFCF, 0xEE46, 0xDCDD, 0xCD54, 0xB9EB, 0xA862, 0x9AF9, 0x8B70,
  0x8408, 0x9581, 0xA71A, 0xB693, 0xC22C, 0xD3A5, 0xE13E, 0xF0B7,
  0x0840, 0x19C9, 0x2B52, 0x3ADB, 0x4E64, 0x5FED, 0x6D76, 0x7CFF,
  0x9489, 0x8500, 0xB79B, 0xA612, 0xD2AD, 0xC324, 0xF1BF, 0xE036,
  0x18C1, 0x0948, 0x3BD3, 0x2A5A, 0x5EE5, 0x4F6C, 0x7DF7, 0x6C7E,
  0xA50A, 0xB483, 0x8618, 0x9791, 0xE32E, 0xF2A7, 0xC03C, 0xD1B5,
  0x2942, 0x38CB, 0x0A50, 0x1BD9, 0x6F66, 0x7EEF, 0x4C74, 0x5DFD,
  0xB58B, 0xA402, 0x9699, 0x8710, 0xF3AF, 0xE226, 0xD0BD, 0xC134,
  0x39C3, 0x284A, 0x1AD1, 0x0B58, 0x7FE7, 0x6E6E, 0x5CF5, 0x4D7C,
  0xC60C, 0xD785, 0xE51E, 0xF497, 0x8028, 0x91A1, 0xA33A, 0xB2B3,
  0x4A44, 0x5BCD, 0x6956, 0x78DF, 0x0C60, 0x1DE9, 0x2F72, 0x3EFB,
  0xD68D, 0xC704, 0xF59F, 0xE416, 0x90A9, 0x8120, 0xB3BB, 0xA232,
  0x5AC5, 0x4B4C, 0x79D7, 0x685E, 0x1CE1, 0x0D68, 0x3FF3, 0x2E7A,
  0xE70E, 0xF687, 0xC41C, 0xD595, 0xA12A, 0xB0A3, 0x8238, 0x93B1,
  0x6B46, 0x7ACF, 0x4854, 0x59DD, 0x2D62, 0x3CEB, 0x0E70, 0x1FF9,
  0xF78F, 0xE606, 0xD49D, 0xC514, 0xB1AB, 0xA022, 0x92B9, 0x8330,
  0x7BC7, 0x6A4E, 0x58D5, 0x495C, 0x3DE3, 0x2C6A, 0x1EF1, 0x0F78
};

/// Extended configuration data
static const ext_config_entry_t ext_config[t1_config_size] = {
  [t1_cfg_tm_interbyte]    = { .min = 1,       .max = TM_MAX,     .def = 200     },
  [t1_cfg_tm_atr]          = { .min = 1,       .max = TM_MAX,     .def = 1000    },
  [t1_cfg_tm_response]     = { .min = 1,       .max = TM_MAX,     .def = 2000    },
  [t1_cfg_tm_response_max] = { .min = 1,       .max = TM_MAX,     .def = 4000    },
  [t1_cfg_use_crc]         = { .min = 0,       .max = 1,          .def = 0       },
  [t1_cfg_ifsc]            = { .min = IFS_MIN, .max = IFS_MAX,    .def = 32      },
  [t1_cfg_ifsd]            = { .min = IFS_MIN, .max = IFS_MAX,    .def = IFS_MAX },
  [t1_cfg_dw_fetures]      = { .min = 0,       .max = 0x7FFFFFFF, .def = 0       },
  [t1_cfg_pps_size]        = { .min = 3,       .max = 5,          .def = 3       },
  [t1_cfg_ta1_value]       = { .min = 0,       .max = 0xFF,       .def = 0x11    },
  [t1_cfg_is_usb_reader]   = { .min = 0,       .max = 1,          .def = 0       },
  [t1_cfg_rx_skip_bytes]   = { .min = 0,       .max = 255,        .def = 0       }
};

/**
 * Returns minimal of two size_t operands
 * @param a  operand A
 * @param b  operand B
 * @return   minimal of A and B
 */
static inline size_t min_size_t(size_t a, size_t b) {
    return a < b ? a : b;
}

/**
 * Returns minimal of two uint32_t operands
 * @param a  operand A
 * @param b  operand B
 * @return   minimal of A and B
 */
static inline uint32_t min_u32(uint32_t a, uint32_t b) {
    return a < b ? a : b;
}

/**
 * Checks is given event code corresponds to error event
 * @param event  event
 * @return       true if given event is an error event
 */
static inline bool is_error(event_t event) {
  return event.code >= t1_ev_err_internal;
}

/**
 * Creates event with given event code
 * @param ev_code  event code
 * @return         event
 */
static inline event_t event(t1_ev_code_t ev_code) {
  return (event_t) { .code = ev_code };
}

/**
 * Creates event with given event code and parameter
 * @param ev_code  event code
 * @param ev_prm   event parameter
 * @return         event
 */
static inline event_t event_ext(t1_ev_code_t ev_code, const void* ev_prm) {
  return (event_t) { .code = ev_code, .prm = ev_prm };
}

/**
 * Adds an event to event list
 *
 * @param p_list    pointer to an event list
 * @param event_in  event to add
 */
static void event_add(event_list_t* p_list, event_t event_in) {
  if(event_in.code != t1_ev_none) {
    // Check for list overflow
    if(p_list->len >= MAX_EVENTS) {
      // Replace last event with error
      p_list->buf[MAX_EVENTS - 1U] = event(t1_ev_err_internal);
      p_list->len = MAX_EVENTS;
    } else {
      p_list->buf[p_list->len++] = event_in;
    }
  }
}

/**
 * Calculates LRC error detection code over a list of buffers
 * @param buf_list  list of input buffers terninated with .buf = NULL entry
 * @param dst       destination buffer
 * @param dst_len   size of destination buffer
 * @return          number of bytes written to destination buffer
 */
static inline size_t calc_lrc(const const_buf_t* buf_list, uint8_t* dst,
                              size_t dst_len) {

  const const_buf_t* p_list = buf_list;
  uint8_t lrc = 0;

  while(p_list->buf) {
    const uint8_t* p_src = p_list->buf;
    size_t src_len = p_list->len;
    ++p_list;
    while(src_len--) {
      lrc ^= *p_src++;
    }
  }

  if(dst && dst_len >= LRC_SIZE) {
      *dst = lrc;
      return 1;
  }
  return 0;
}

/**
 * Calculates CRC error detection code over a list of buffers
 * @param buf_list  list of input buffers terninated with .buf = NULL entry
 * @param dst       destination buffer
 * @param dst_len   size of destination buffer
 * @return          number of bytes written to destination buffer
 */
static inline size_t calc_crc(const const_buf_t* buf_list,
                              uint8_t* dst, size_t dst_len) {
  const const_buf_t* p_list = buf_list;
  uint16_t crc = 0xFFFF;

  while(p_list->buf) {
    const uint8_t* p_src = p_list->buf;
    size_t src_len = p_list->len;
    ++p_list;
    while (src_len--) {
      crc = ((crc >> 8) & 0xFF) ^ crc_tbl[(crc ^ *p_src++) & 0xFF];
    }
  }

  if(dst && dst_len >= CRC_SIZE) {
    dst[0] = (crc >> 8) & 0xFF;
    dst[1] = crc & 0xFF;
    return CRC_SIZE;
  }
  return 0;
}

/**
 * Calculates error detection code for epilogue over a list of buffers
 * @param inst      protocol instance
 * @param buf_list  list of input buffers terninated with .buf = NULL entry
 * @param dst       destination buffer
 * @param dst_len   size of destination buffer
 * @return          number of bytes written to destination buffer
 */
static inline size_t calc_edc_multi(const t1_inst_t* inst,
                                    const const_buf_t* buf_list,
                                    uint8_t* dst, size_t dst_len) {
  return inst->config[t1_cfg_use_crc] ?
    calc_crc(buf_list, dst, dst_len) :
    calc_lrc(buf_list, dst, dst_len);
}

/**
 * Calculates error detection code for epilogue
 * @param inst      protocol instance
 * @param src       source buffer
 * @param src_len   number of bytes in source buffer to process
 * @param dst       destination buffer
 * @param dst_len   size of destination buffer
 * @return          number of bytes written to destination buffer
 */
static size_t calc_edc(const t1_inst_t* inst, const uint8_t* src,
                       size_t src_len, uint8_t* dst, size_t dst_len) {
  const_buf_t buf_list[] = {
    { .buf = src, .len = src_len },
    { .buf = NULL } // terminator
  };
  return calc_edc_multi(inst, buf_list, dst, dst_len);
}

/**
 * Returns size of EDC code
 * @param inst  protocol instance
 * @return      size of EDC code in bytes
 */
static inline size_t edc_size(const t1_inst_t* inst) {
  return inst->config[t1_cfg_use_crc] ? CRC_SIZE : LRC_SIZE;
}

/**
 * Re-initializes receive part of protocol instance before next reception
 * @param inst              protocol instance
 */
static void reset_rx(t1_inst_t* inst) {
  inst->rx_buf_idx = 0;
  inst->rx_block_prm.block_type = t1_block_unkn;
  inst->rx_block_prm.inf_len = 0;
  inst->rx_state = t1_rxs_skip;
  inst->rx_expected_bytes = -1;
  inst->tmr_interbyte_timeout = 0;
}

void t1_reset(t1_inst_t* inst, bool wait_atr) {
  if(inst) {
    inst->fsm_state = wait_atr ? t1_st_wait_atr : t1_st_idle;
    fifo_clear(&inst->tx_fifo);
    inst->tx_fifo_nblock = 0;
    inst->tx_seq_number = 0;
    inst->tx_last_seq_number = 0;
    inst->tx_attempts = 0;
    inst->tx_prev_block_prm.block_type = t1_block_unkn;
    inst->tx_prev_block_prm.inf_len = 0;
    inst->tx_block_ctr = 0;
    reset_rx(inst);
    inst->rx_apdu_prm.len = 0;
    inst->rx_seq_number = 0;
    inst->rx_new_apdu = true;
    inst->rx_bad_block = false;
    inst->tmr_atr_timeout = wait_atr ? inst->config[t1_cfg_tm_atr] : 0;
    inst->tmr_response_timeout = 0;
  }
}

/**
 * Codes T=1 protocol block and pushes it into transmit FIFO buffer
 * @param inst        protocol instance
 * @param type        block type
 * @param pcb         PCB byte
 * @param inf         information field
 * @param inf_len     length of information field in bytes
 * @param more_data   flag indicating that more data will follow in next blocks
 * @param seq_number  sequence number "N(S)" or "N(R)", 0 or 1
 * @return            true if successfull
 */
static bool push_block(t1_inst_t* inst, t1_block_type_t type, uint8_t pcb,
                       const uint8_t* inf, size_t inf_len, bool more_data,
                       uint8_t seq_number)
{
  if(inf_len <= inst->config[t1_cfg_ifsc]) {
    size_t block_size = 0;
    uint8_t prologue[prologue_size];
    uint8_t epilogue[MAX_EDC_LEN];
    size_t epilogue_size = 0;
    block_hdr_t hdr = {
      .type = type,
      .more_data = more_data ? 1U : 0U,
      .seq_number = seq_number
    };

    // Create prologue & epilogue
    prologue[prologue_nad] = TX_NAD_VALUE;
    prologue[prologue_pcb] = pcb;
    prologue[prologue_len] = inf_len;
    const_buf_t buf_list[] = {
      { .buf = prologue, .len = prologue_size },
      { .buf = inf,      .len = inf_len       },
      { .buf = NULL } // terminator
    };
    epilogue_size = calc_edc_multi(inst, buf_list, epilogue, sizeof(epilogue));
    block_size = prologue_size + inf_len + epilogue_size;

    // Put block in FIFO buffer
    if( epilogue_size && block_size <= MAX_IBLOCK_SIZE &&
        (block_size + sizeof(hdr)) <= fifo_nfree(&inst->tx_fifo) ) {
      // Fill size and push header
      hdr.size = block_size;
      fifo_push_buf(&inst->tx_fifo, (const uint8_t*)&hdr, sizeof(hdr));
      // Push I-block
      fifo_push_buf(&inst->tx_fifo, prologue, prologue_size);
      fifo_push_buf(&inst->tx_fifo, inf, inf_len);
      fifo_push_buf(&inst->tx_fifo, epilogue, epilogue_size);
      // Increment block count
      ++inst->tx_fifo_nblock;
      return true;
    }
  }
  return false;
}

/**
 * Codes I-block and pushes it into transmit FIFO buffer
 * @param inst     protocol instance
 * @param inf      information field
 * @param inf_len  length of information field in bytes
 * @return         true if successfull
 */
static bool push_iblock(t1_inst_t* inst, const uint8_t* inf, size_t inf_len,
                        bool more_data)
{
  uint8_t pcb = (inst->tx_seq_number ? IB_NS_BIT : 0) |
                (more_data ? IB_M_BIT : 0);

  if(push_block(inst, t1_block_i, pcb, inf, inf_len, more_data,
                inst->tx_seq_number)) {
    inst->tx_seq_number ^= 1;
    return true;
  }
  return false;
}

/**
 * Calculates total size of chained I-blocks
 * @param inst      protocol instance
 * @param apdu_len  size of APDU in bytes
 * @param ifsc      IFSC, card's maximum information block size
 * @return          total size of chained I-blocks in bytes or 0 if failure
 */
static inline size_t iblock_chain_size(const t1_inst_t* inst, size_t apdu_len,
                                       size_t ifsc) {
  if(ifsc) {
    size_t iblock_overhead = prologue_size + edc_size(inst);
    size_t whole_blocks = apdu_len / ifsc;
    size_t extra_bytes = apdu_len % ifsc;

    return whole_blocks * (ifsc + iblock_overhead) +
           (extra_bytes ? extra_bytes + iblock_overhead : 0);
  }
  return 0;
}

/**
 * Codes APDU and pushes produced I-blocks into transmit FIFO buffer w/chaining
 * @param inst            protocol instance
 * @param apdu            buffer containing APDU
 * @param apdu_len        length of APDU in bytes
 * @param p_err_internal  pointer to flag, set to true on internal out error
 * @return                true if successfull
 */
static bool push_iblock_chain(t1_inst_t* inst, const uint8_t* apdu,
                              size_t apdu_len)
{
  const size_t ifsc = inst->config[t1_cfg_ifsc];
  size_t tot_size = iblock_chain_size(inst, apdu_len, ifsc);

  if(tot_size && tot_size <= fifo_nfree(&inst->tx_fifo)) {
    size_t rm_bytes = apdu_len;
    const uint8_t* p_apdu = apdu;
    while(rm_bytes) {
      size_t inf_len = rm_bytes > ifsc ? ifsc : rm_bytes;
      if(!push_iblock(inst, p_apdu, inf_len, rm_bytes > ifsc)) {
        return false;
      }
      p_apdu += inf_len;
      rm_bytes -= inf_len;
    }
    return true;
  }
  return false;
}

/**
 * Sends S-block directly via serial out callback function
 * @param inst      protocol instance
 * @param command   request command
 * @param inf_byte  information byte or -1 if INF fielsd is absent
 * @return          event or empty event with event_t::code = t1_ev_none
 */
static event_t send_sblock(t1_inst_t* inst, t1_sblock_cmd_t command,
                           bool is_response, int16_t inf_byte) {
  uint8_t buf[prologue_size + 1 + MAX_EDC_LEN];

  buf[prologue_nad]  = TX_NAD_VALUE;
  buf[prologue_pcb]  = SB_MARKER | (uint8_t)command |
                       (is_response ? SB_RESP_BIT : 0);
  buf[prologue_len]  = (inf_byte >= 0) ? 1 : 0;
  buf[prologue_size] = (uint8_t)inf_byte;

  uint8_t* p_edc = buf + prologue_size + buf[prologue_len];
  size_t edc_len = calc_edc(inst, buf, p_edc - buf, p_edc, MAX_EDC_LEN);

  // Transmit block, advance counter, set timeout
  if(!inst->cb_serial_out(buf, p_edc - buf + edc_len, inst->p_user_prm)) {
    return event(t1_ev_err_serial_out);
  }
  if(inst->tx_block_ctr < UINT8_MAX) { ++inst->tx_block_ctr; }
  inst->tmr_response_timeout = inst->config[t1_cfg_tm_response];

  // Save parameters of transmitted block
  inst->tx_prev_block_prm.block_type = t1_block_s;
  inst->tx_prev_block_prm.inf_len = buf[prologue_len];
  inst->tx_prev_block_prm.sblock_prm.command = command;
  inst->tx_prev_block_prm.sblock_prm.is_response = is_response;
  inst->tx_prev_block_prm.sblock_prm.inf_byte = inf_byte;

  return event_none;
}

/**
 * Sends R-block directly via serial out callback function
 * @param inst        protocol instance
 * @param ack_code    acknowledgement code
 * @param seq_number  sequence number, N(R)
 * @return            event or empty event with event_t::code = t1_ev_none
 */
static event_t send_rblock(t1_inst_t* inst, t1_rblock_ack_t ack_code,
                           uint8_t seq_number) {
  uint8_t buf[prologue_size + MAX_EDC_LEN];

  buf[prologue_nad] = TX_NAD_VALUE;
  buf[prologue_pcb] = RB_MARKER | (seq_number ? RB_NS_BIT : 0) | (int)ack_code;
  buf[prologue_len] = 0;
  size_t edc_len = calc_edc(inst, buf, prologue_size, buf + prologue_size,
                            MAX_EDC_LEN);

  // Transmit block
  if(!inst->cb_serial_out(buf, prologue_size + edc_len, inst->p_user_prm)) {
    return event(t1_ev_err_serial_out);
  }
  inst->tmr_response_timeout = inst->config[t1_cfg_tm_response];

  // Save parameters of transmitted block
  inst->tx_prev_block_prm.block_type = t1_block_r;
  inst->tx_prev_block_prm.inf_len = 0;
  inst->tx_prev_block_prm.rblock_prm.ack_code = ack_code;
  inst->tx_prev_block_prm.rblock_prm.seq_number = seq_number;

  return event_none;
}

/**
 * Checks if there is at least one block available in TX FIFO buffer
 * @param inst  protocol instance
 * @return      true if at least one block is available
 */
static inline bool tx_fifo_has_block(const t1_inst_t* inst) {
  return fifo_nused(&inst->tx_fifo) > sizeof(block_hdr_t);
}

/**
 * Outputs last block from FIFO buffer to serial port
 * @param inst  protocol instance
 * @return      event or empty event with event_t::code = t1_ev_none
 */
static event_t tx_fifo_send_last_block(t1_inst_t* inst) {
  if(tx_fifo_has_block(inst)) {
    uint8_t buf[256];
    block_hdr_t hdr;
    size_t read_idx = fifo_get_read_idx(&inst->tx_fifo);

    fifo_read_buf(&inst->tx_fifo, &read_idx, (uint8_t*)&hdr, sizeof(hdr),
                  sizeof(hdr));

    // Transmit block, advance counter, set timeout
    size_t block_size = hdr.size;
    while(block_size) {
      size_t out_len = min_size_t(block_size, sizeof(buf));
      fifo_read_buf(&inst->tx_fifo, &read_idx, buf, sizeof(buf), out_len);
      if(!inst->cb_serial_out(buf, out_len, inst->p_user_prm)) {
        return event(t1_ev_err_serial_out);
      }
      block_size -= out_len;
    }
    if(inst->tx_block_ctr < UINT8_MAX) { ++inst->tx_block_ctr; }
    inst->tmr_response_timeout = inst->config[t1_cfg_tm_response];

    // Save parameters of transmitted block
    inst->tx_prev_block_prm.block_type = t1_block_i;
    inst->tx_prev_block_prm.inf_len = hdr.size - prologue_size - edc_size(inst);
    inst->tx_prev_block_prm.iblock_prm.more_data = hdr.more_data;
    inst->tx_prev_block_prm.iblock_prm.seq_number = hdr.seq_number;
    inst->tx_last_seq_number = hdr.seq_number;
  }
  return event_none;
}

/**
 * Removes last block from transmit FIFO buffer
 * @param inst  protocol instance
 */
static void tx_fifo_remove_last_block(t1_inst_t* inst) {
  if(tx_fifo_has_block(inst)) {
    size_t read_idx = fifo_get_read_idx(&inst->tx_fifo);
    block_hdr_t hdr;
    fifo_read_buf(&inst->tx_fifo, &read_idx, (uint8_t*)&hdr, sizeof(hdr),
                  sizeof(hdr));
    fifo_remove(&inst->tx_fifo, sizeof(hdr) + hdr.size);
    --inst->tx_fifo_nblock;
  }
}

bool t1_init(t1_inst_t* inst, t1_cb_serial_out_t cb_serial_out,
             t1_cb_handle_event_t cb_handle_event, void* p_user_prm) {
  if(inst && cb_serial_out && cb_handle_event) {
    inst->cb_serial_out = cb_serial_out;
    inst->cb_handle_event = cb_handle_event;
    inst->p_user_prm = p_user_prm;
    for(int i = 0; i < t1_config_size; i++) {
      inst->config[i] = ext_config[i].def;
    }
    fifo_init(&inst->tx_fifo, inst->tx_fifo_buf, T1_TX_FIFO_SIZE);
    inst->rx_apdu_prm.apdu = inst->rx_apdu;
    t1_reset(inst, true);
    return true;
  }
  return false;
}

bool t1_set_config(t1_inst_t* inst, t1_config_prm_id_t prm_id, int32_t value) {
  if(inst && prm_id >= 0 &&  prm_id < t1_config_size) {
    // Ensure that range is defined and value is within allowed range
    if((ext_config[prm_id].min || ext_config[prm_id].max) &&
       value >= ext_config[prm_id].min && value <= ext_config[prm_id].max) {
      inst->config[prm_id] = value;
      return true;
    }
  }
  return false;
}

bool t1_set_default_config(t1_inst_t* inst, t1_config_prm_id_t prm_id) {
  if(inst && prm_id >= 0 &&  prm_id < t1_config_size) {
    inst->config[prm_id] = ext_config[prm_id].def;
    return true;
  }
  return false;
}

int32_t t1_get_config(const t1_inst_t* inst, t1_config_prm_id_t prm_id) {
  if(inst && prm_id >= 0 &&  prm_id < t1_config_size) {
    return inst->config[prm_id];
  }
  return -1;
}

/**
 * Returns number of interface bytes from given indicator Y
 * @param y  indicator, "Y"
 * @return   number of interface bytes
 */
static inline size_t atr_ibyte_num(uint8_t y) {
  return ((y >> 3) & 1) + ((y >> 2) & 1) + ((y >> 1) & 1) + (y & 1);
}

/**
 * Initializes ATR structure with default values
 * @param p_atr    pointer to ATR structure to initialize
 * @param atr_buf  buffer containing ATR
 * @param atr_len  length of ATR in bytes
 */
static inline void atr_decoded_init(t1_atr_decoded_t* p_atr,
                                    const uint8_t* atr_buf, size_t atr_len) {
  p_atr->atr = atr_buf;
  p_atr->atr_len = atr_len;
  p_atr->convention = t1_cnv_direct;
  p_atr->t0_supported = false;
  p_atr->t1_supported = false;
  p_atr->hist_bytes = NULL;
  p_atr->hist_nbytes = 0;
  for(int i = 0; i < t1_atr_intf_bytes; i++) {
    p_atr->global_bytes[i] = -1;
    p_atr->t1_bytes[i] = -1;
  }
}

/**
 * Parses ATR message
 *
 * Limitations: only direct convention is supported, TS byte is ignored
 * @param buf    buffer containing ATR
 * @param len    length of ATR in bytes
 * @param p_atr  pointer to ATR structure filled by this function
 * @return       true if successful
 */
static bool parse_atr(const uint8_t *buf, size_t len, t1_atr_decoded_t* p_atr) {
  // Size of one interface record, set of TAi, TBi and TCi bytes
  const size_t intf_size = t1_atr_ta2 - t1_atr_ta1;
  // Dummy buffer to receive unneeded interface bytes, safer than NULL
  int16_t intf_null[intf_size];
  // Pointer to buffer receiving interface bytes
  int16_t* p_intf = intf_null;
  // Index of current interface block, named as "i" in standard
  size_t intf_idx = 1;
  // Index within t1_ev_prm_atr_t::global_bytes[] array
  size_t global_idx = 0;
  // Index within t1_ev_prm_atr_t::t1_bytes[] array
  size_t t1_idx = 0;
  // Expected length in bytes
  size_t exp_len = ATR_MIN_BYTES;
  // Indicator of presence of TAi...TDi bytes, named as "Y" in standard
  uint8_t indicator = 0;
  // XOR checksum
  uint8_t checksum = 0;
  // Flag indicating presence of TCK byte
  bool tck_present = false;
  // Pointer to current byte
  const uint8_t *p_byte = buf;

  // Fill "atr" and "atr_len", set other fields to defaults
  atr_decoded_init(p_atr, buf, len);

  // Parse all expected bytes of ATR but not more than contained in buffer
  for(size_t n = 0; n < len && exp_len <= len && n < exp_len; n++, p_byte++) {
    if(n == 0) { // TS, initial character
      if(*p_byte == TS_CONVENTION_INVERSE) {
        p_atr->convention = t1_cnv_inverse;
      } else if(*p_byte != TS_CONVENTION_DIRECT) {
        return false;
      }
    } else if(n == 1) { // T0, format byte
      exp_len += p_atr->hist_nbytes = *p_byte & 0x0F;
      indicator = *p_byte >> 4;
      if(indicator) {
          p_intf = &p_atr->global_bytes[global_idx];
          global_idx += intf_size;
          exp_len += atr_ibyte_num(indicator);
      }
      if(!(indicator & TD_BIT)) { // TD1 is absent, only T=0 is supported
        p_atr->t0_supported = true;
      }
    } else {
      if(indicator & TA_BIT) { // TA byte
        p_intf[t1_atr_ta1] = *p_byte;
        indicator ^= TA_BIT;
      } else if(indicator & TB_BIT) { // TB byte
        p_intf[t1_atr_tb1] = *p_byte;
        indicator ^= TB_BIT;
      } else if(indicator & TC_BIT) { // TC byte
        p_intf[t1_atr_tc1] = *p_byte;
        indicator ^= TC_BIT;
      } else if(indicator & TD_BIT) { // TD byte
        p_intf = intf_null;
        indicator = *p_byte >> 4;
        if(indicator) {
          protocol_id_t prot_id = (protocol_id_t)(*p_byte & 0x0F);
          exp_len += atr_ibyte_num(indicator);
          ++intf_idx;
          if(prot_id == atr_prot_t0) {
            p_atr->t0_supported = true;
          } else if(prot_id == atr_prot_t1) {
            p_atr->t1_supported = true;
          }
          if(prot_id == atr_prot_t1 && intf_idx > 2) {
            if(t1_idx + intf_size <= t1_atr_intf_bytes) {
              p_intf = &p_atr->t1_bytes[t1_idx];
              t1_idx += intf_size;
            }
          } else if(prot_id == atr_globals || intf_idx <= 2) {
            if(global_idx + intf_size <= t1_atr_intf_bytes) {
              p_intf = &p_atr->global_bytes[global_idx];
              global_idx += intf_size;
            }
          }
          if(prot_id != atr_prot_t0 && !tck_present) { // Is TCK present?
            tck_present = true;
            ++exp_len;
          }
        }
      } else if(p_atr->hist_bytes == NULL) { // Historical bytes
        p_atr->hist_bytes = p_byte;
      }
    }

    if(n > 0) { // Calculate checksum
      checksum ^= *p_byte;
    }
  }

  // Ensure that ATR is not truncated and TCK is correct (if exists)
  if(exp_len <= len && (!tck_present || checksum == 0) ) {
    return true;
  }
  return false;
}

/**
 * Handles ATR message checking compatibility of the smart card
 * @param inst          protocol instance
 * @param p_atr         pointer to ATR structure filled by this function
 * @param p_needs_ppsx  pointer to flag requesting PPS exchange
 * @return              true if card is compatible with this T=1 implementation
 */
static bool handle_atr(t1_inst_t* inst, t1_atr_decoded_t* p_atr,
                       bool* p_needs_ppsx) {
  if(p_needs_ppsx) {
    *p_needs_ppsx = false;
  }

  if(p_atr->t1_supported) {
    if(p_atr->t1_bytes[t1_atr_ta1] != -1) {
      inst->config[t1_cfg_ifsc] = p_atr->t1_bytes[t1_atr_ta1];
    }
    if(p_atr->t1_bytes[t1_atr_tc1] != -1) {
      inst->config[t1_cfg_use_crc] = p_atr->t1_bytes[t1_atr_tc1] & 1;
    }

    // If card is in negotiable mode we need to start PPS exchange
    if(p_atr->t1_bytes[t1_atr_ta2] == -1 && p_needs_ppsx) {
      *p_needs_ppsx = true;
    }
    // If the USB card reader has Auto PPS feature in the dwFeatures field, it is non necessary to send PPS
    // It will be done automatically by the card reader
    if(inst->config[t1_cfg_dw_fetures] & CCID_CLASS_AUTO_PPS_CUR){
      *p_needs_ppsx = false;
    }
    return true;
  }
  return false;
}

/**
 * Handles corrupted, incorrect or lost block
 * @param inst        protocol instance
 * @param block_type  type of received block or t1_block_unkn if unknown
 * @param ack_code    suggested acknowledgement code for R-block
 * @return            event or empty event with event_t::code = t1_ev_none
 */
static event_t handle_bad_block(t1_inst_t* inst, t1_block_type_t block_type,
                                t1_rblock_ack_t ack_code) {
  inst->tmr_response_timeout = 0;
  inst->rx_bad_block = true; // Flag received block as bad

  if(inst->fsm_state != t1_st_resync) {
    if(inst->tx_attempts + 1 < DELIVERY_ATTEMPTS) {
      ++inst->tx_attempts;
      return send_rblock(inst, ack_code, inst->rx_seq_number);
    } else if(inst->tx_block_ctr <= 1) { // Failed delivering very first block
      return event(t1_ev_err_comm_failure);
    } else { // Do resynchronization
      inst->tx_attempts = 0;
      inst->fsm_state = t1_st_resync;
      return send_sblock(inst, t1_sblock_cmd_resynch, false, -1);
    }
  } else { // Resynchronization
    if(inst->tx_attempts + 1 < RESYNC_ATTEMPTS) {
      ++inst->tx_attempts;
      return send_sblock(inst, t1_sblock_cmd_resynch, false, -1);
    } else {
      return event(t1_ev_err_comm_failure);
    }
  }
  // Should always transmit something
  return event(t1_ev_err_internal);
}

/**
 * Helper function calling user event handler for provided given event
 *
 * This function handles protocol events by notifying host. In case of error
 * event it also transfers FSM into error state.
 * IMPORTANT: This function must be called straight before returning from API
 * functions to allow calling other API functions within the user handler.
 * @param inst   protocol instance
 * @param event  event code
 */
static void handle_event(t1_inst_t* inst, event_t event) {
  if(event.code != t1_ev_none) {
    if(is_error(event)) {
      t1_reset(inst, false);
      inst->fsm_state = t1_st_error;
    }
    inst->cb_handle_event(event.code, event.prm, inst->p_user_prm);
  }
}

/**
 * Helper function calling user event handlers for provided given event list
 *
 * This function handles protocol events by notifying host. In case of error
 * event it also transfers FSM into error state.
 * IMPORTANT: This function must be called straight before returning from API
 * functions to allow calling other API functions within the user handler.
 * @param inst    protocol instance
 * @param p_list  pointer to an event list
 */
static void handle_events(t1_inst_t* inst, const event_list_t* p_list) {
  for(size_t i = 0U; i < p_list->len; ++i) {
    handle_event(inst, p_list->buf[i]);
  }
}

/**
 * Decreases timer counter and checks if it is elapsed
 *
 * This function also ensures that it is called at least twice before indicating
 * that timer is elapsed. It is done as protection measure against abnormally
 * quick timeout event in case timer task is called right after the timer
 * variable is initialized. As side effect, this function supports timeouts not
 * longer than 0x7FFFFFFF.
 * @param p_timer     pointer to timer variable
 * @param elapsed_ms  time in milliseconds passed since previous call
 * @return            true is timer is elapsed
 */
static bool timer_elapsed(uint32_t *p_timer, uint32_t elapsed_ms) {
  if(*p_timer) {
    uint32_t time = *p_timer & 0x7FFFFFFFUL;
    if(!(time -= min_u32(elapsed_ms, time))) {
      if(*p_timer & 0x80000000UL) { // Not first call?
        *p_timer = 0;
        return true;
      }
    }
    // Set higher bit to check for non-first call later
    *p_timer = time | 0x80000000UL;
  }
  return false;
}

/**
 * Sends PPS request
 *
 * @param inst  protocol instance
 * @return      event or empty event with event_t::code = t1_ev_none
 */
static event_t send_pps_request(t1_inst_t* inst) {
  uint8_t buf[inst->config[t1_cfg_pps_size]];

  // Create request
  if(!inst->config[t1_cfg_is_usb_reader])
  {
      buf[pps_ppss] = PPSS;               // PPS identifier
      buf[pps_pps0] = atr_prot_t1;        // T=1 protocol, PPS1-PPS3 are absent
      buf[pps_pck ] = PPSS ^ atr_prot_t1; // XOR checksum
  }
  else
  {
     buf[usb_pps_ppss] = PPSS;               // PPS identifier
     buf[usb_pps_pps0] = atr_prot_t1 | 0x10; // T=1 protocol, PPS2-PPS3 are absent
     buf[usb_pps_pps1] = inst->config[t1_cfg_ta1_value];
     buf[usb_pps_pck ] = PPSS ^ buf[usb_pps_pps0] ^ buf[usb_pps_pps1]; // XOR checksum
  }

  // Transmit request
  if(!inst->cb_serial_out(buf, sizeof(buf), inst->p_user_prm)) {
    return event(t1_ev_err_serial_out);
  }
  inst->tmr_response_timeout = inst->config[t1_cfg_tm_response];

  reset_rx(inst);
  return event_none;
}

/**
 * Sends IFSD request
 *
 * @param inst  protocol instance
 * @return      event or empty event with event_t::code = t1_ev_none
 */
static event_t send_ifsd_request(t1_inst_t* inst) {
  event_t ev = send_sblock(inst, t1_sblock_cmd_ifs, false, inst->config[t1_cfg_ifsd]);
  if(!is_error(ev)) {
    inst->tmr_response_timeout = inst->config[t1_cfg_tm_response];
  }
  return ev;
}

/**
 * Sends block from FIFO buffer if available
 *
 * @param inst  protocol instance
 * @return      event or empty event with event_t::code = t1_ev_none
 */
static event_t send_block_if_available(t1_inst_t* inst) {
  if(t1_st_error != inst->fsm_state) {
    if(tx_fifo_has_block(inst)) {
      inst->fsm_state = t1_st_wait_response;
      return tx_fifo_send_last_block(inst);
    } else {
      inst->fsm_state = t1_st_idle;
      return event_none;
    }
  }
}

/**
 * Checks PPS response
 * @param inst  protocol instance
 * @param buf   buffer holding PPS response
 * @param size  size of PPS response
 * @return      true if PPS response is valid
 */
static bool check_pps_response(t1_inst_t* inst, const uint8_t* buf,
                               size_t size) {
  if( pps_size == size &&
      PPSS == buf[pps_ppss] &&
      atr_prot_t1 == buf[pps_pps0] &&
      0U == buf[pps_ppss] ^ buf[pps_pps0] ^ buf[pps_pck ] ) {
    return true;
  }
  return false;
}
/**
 * Checks Usb PPS response. 
 * If we use USB cardreader, we need to check additional PPS1 field.
 * @param inst  protocol instance
 * @param buf   buffer holding PPS response
 * @param size  size of PPS response
 * @return      true if PPS response is valid
 */
static bool check_usb_pps_response(t1_inst_t* inst, const uint8_t* buf,
                               size_t size) {
  if( usb_pps_size == size &&
      PPSS == buf[usb_pps_ppss] &&
      atr_prot_t1 | 0x10 == buf[usb_pps_pps0] &&
      inst->config[t1_cfg_ta1_value] == buf[usb_pps_pps1] &&
      0U == buf[usb_pps_ppss]^ buf[usb_pps_pps1] ^ buf[usb_pps_pps0] ^ buf[usb_pps_pck] ) {
    return true;
  }
  return false;
}
/**
 * Handles PPS data
 * @param inst       protocol instance
 * @param buf        buffer holding received bytes
 * @param len        number of bytes received
 * @param p_events   event list
 * @return           event or empty event with event_t::code = t1_ev_none
 */
static void handle_pps_data(t1_inst_t* inst, const uint8_t* buf,
                            size_t len, event_list_t* p_events) {

  if(inst->config[t1_cfg_pps_size] <= T1_RX_BUF_SIZE && inst->rx_buf_idx < T1_RX_BUF_SIZE) {
    const uint8_t* p_byte = buf;
    while(inst->rx_buf_idx < inst->config[t1_cfg_pps_size] && p_byte < (buf + len)) {
      inst->rx_buf[inst->rx_buf_idx++] = *p_byte++;
    }
    if(inst->rx_buf_idx == inst->config[t1_cfg_pps_size]) { // Handle PPS response
      inst->tmr_response_timeout = 50U;
      int res;
      if(inst->rx_buf_idx == 3)
      {
        res = check_pps_response(inst, inst->rx_buf, inst->rx_buf_idx);
      }
      else
      {
        res = check_usb_pps_response(inst, inst->rx_buf, inst->rx_buf_idx);
      }
      if(res) {
        reset_rx(inst);
        event_add(p_events, event(t1_ev_pps_exchange_done));
        inst->fsm_state = t1_st_ifsd_setup_prepare;
      } else {
        event_add(p_events, event(t1_ev_pps_failed));
      }
    }
  } else {
    event_add(p_events, event(t1_ev_err_internal));
  }
}

void t1_timer_task(t1_inst_t* inst, uint32_t elapsed_ms) {
  if(inst && inst->fsm_state != t1_st_error && elapsed_ms) {
    event_list_t events = { .len = 0U };
    t1_atr_decoded_t atr_decoded;

    if(inst->fsm_state == t1_st_ifsd_setup_prepare)
    {
      event_add(&events, send_ifsd_request(inst));
      inst->fsm_state = t1_st_ifsd_setup;
    }
    // Process all timers
    if(timer_elapsed(&inst->tmr_interbyte_timeout, elapsed_ms)) {
      if(inst->fsm_state == t1_st_wait_atr) {
        if(parse_atr(inst->rx_buf, inst->rx_buf_idx, &atr_decoded)) {
          inst->config[t1_cfg_ta1_value] = atr_decoded.atr[2];
          bool needs_ppsx = false;
          if(handle_atr(inst, &atr_decoded, &needs_ppsx)) {
            event_add(&events, event_ext(t1_ev_atr_received, &atr_decoded));
            if(needs_ppsx) {
              event_add(&events, send_pps_request(inst));
              inst->fsm_state = t1_st_pps_exchange;
            } else { // needs_ppsx
              event_add(&events, event(t1_ev_pps_exchange_done));
              inst->fsm_state = t1_st_ifsd_setup_prepare;
            }
          } else { // handle_atr(...)
            event_add(&events, event_ext(t1_ev_err_incompatible, &atr_decoded));
          }
        } else { // parse_atr(...)
          event_add(&events, event(t1_ev_err_bad_atr));
        }
      } else if (inst->fsm_state == t1_st_pps_exchange) {
        event_add(&events, event(t1_ev_pps_failed));
      } else if (inst->fsm_state == t1_st_ifsd_setup) {
        event_add(&events, event(t1_ev_err_comm_failure));
      } else if (inst->fsm_state == t1_st_wait_response) {
        event_add( &events, handle_bad_block( inst, t1_block_unkn,
                                              t1_rblock_ack_err_other ) );
      }
      reset_rx(inst);
    }
    if(timer_elapsed(&inst->tmr_atr_timeout, elapsed_ms)) {
      event_add(&events, event(t1_ev_err_atr_timeout));
    }
    if(timer_elapsed(&inst->tmr_response_timeout, elapsed_ms)) {
      if(inst->fsm_state == t1_st_pps_exchange) {
        event_add(&events, event(t1_ev_pps_failed));
      } else if (inst->fsm_state == t1_st_ifsd_setup) {
        event_add(&events, event(t1_ev_err_comm_failure));
      } else {
        event_add( &events, handle_bad_block( inst, t1_block_unkn,
                                              t1_rblock_ack_err_other ) );
      }
      reset_rx(inst);
    }

    // Call event handler straight before returning
    handle_events(inst, &events);
  }
}

uint32_t t1_can_sleep_ms(const t1_inst_t* inst) {
  if(inst) {
    if(inst->tmr_interbyte_timeout ||
       inst->tmr_atr_timeout ||
       inst->tmr_response_timeout) {
      return DEF_SLEEP_TIME_MS;
    }
  }
  return UINT32_MAX;
}

/**
 * Handles ATR data
 * @param inst       protocol instance
 * @param buf        buffer holding received bytes
 * @param len        number of bytes received
 * @return           event or empty event with event_t::code = t1_ev_none
 */
static event_t handle_atr_data(t1_inst_t* inst, const uint8_t* buf,
                               size_t len) {

  if(inst->rx_buf_idx + len > T1_RX_BUF_SIZE) {
    return event(t1_ev_err_bad_atr);
  }

  const uint8_t* p_byte = buf;
  while(p_byte < buf + len) {
    inst->rx_buf[inst->rx_buf_idx++] = *p_byte++;
  }
  inst->tmr_atr_timeout = 0;
  // ATR will be parsed by timer, when smart card stops transmitting bytes

  return event_none;
}

/**
 * Saves received INF bytes to APDU buffer
 * @param inst     protocol instance
 * @param inf      information field
 * @param inf_len  length of information field in bytes
 * @return         true - successfull, false - no space in the buffer
 */
static bool save_apdu_data(t1_inst_t* inst, const uint8_t* inf,
                           size_t inf_len) {
  if(inst->rx_new_apdu) {
    inst->rx_new_apdu = false;
    inst->rx_apdu_prm.len = 0;
  }

  if(inst->rx_apdu_prm.len + inf_len <= sizeof(inst->rx_apdu)) {
    const uint8_t *p_inf = inf;
    uint8_t *p_apdu = inst->rx_apdu + inst->rx_apdu_prm.len;
    for(size_t i = 0; i < inf_len; i++) {
      *p_apdu++ = *p_inf++;
    }
    inst->rx_apdu_prm.len += inf_len;
    return true;
  }
  return false;
}

/**
 * Handles received I-block
 * @param inst        protocol instance
 * @param seq_number  sequence number, "N(S)"
 * @param more_data   more-data bit, "M"
 * @param inf         information field
 * @param inf_len     length of information field in bytes
 * @return            event or empty event with event_t::code = t1_ev_none
 */
static event_t handle_iblock(t1_inst_t* inst, uint8_t seq_number,
                             bool more_data, const uint8_t* inf,
                             size_t inf_len) {
  if(inst->fsm_state == t1_st_wait_response) {
    inst->tmr_response_timeout = 0;
    if(seq_number == inst->rx_seq_number) {
      inst->rx_seq_number ^= 1;
      if(save_apdu_data(inst, inf, inf_len)) {
        if(more_data) {
          return send_rblock(inst, t1_rblock_ack_ok, inst->rx_seq_number);
        } else {
          inst->rx_new_apdu = true;
          tx_fifo_remove_last_block(inst);
          event_t ev = send_block_if_available(inst);
          return is_error(ev) ?
                 ev : event_ext(t1_ev_apdu_received, &inst->rx_apdu_prm);
        }
      } else {
        return event(t1_ev_err_oversized_apdu);
      }
    }
  }
  return handle_bad_block(inst, t1_block_i, t1_rblock_ack_err_other);
}

/**
 * Re-sends previous block directly via serial out callback function
 * @param inst  protocol instance
 * @return      event or empty event with event_t::code = t1_ev_none
 */
static event_t resend_prev_block(t1_inst_t* inst) {
  const t1_block_prm_t *p_prev = &inst->tx_prev_block_prm;

  switch(p_prev->block_type) {
    case t1_block_i:
      if(tx_fifo_has_block(inst)) {
        return tx_fifo_send_last_block(inst);
      }
      break;

    case t1_block_r:
      return send_rblock(inst, p_prev->rblock_prm.ack_code,
                         p_prev->rblock_prm.seq_number);

    case t1_block_s:
      return send_sblock(inst, p_prev->sblock_prm.command,
                         p_prev->sblock_prm.is_response,
                         p_prev->sblock_prm.inf_byte);
    default:
      break;
  }
  return event_none;
}

/**
 * Handles received R-block
 * @param inst        protocol instance
 * @param seq_number  sequence number, "N(R)"
 * @param ack_code    acknowledgement code
 * @return            event or empty event with event_t::code = t1_ev_none
 */
static event_t handle_rblock(t1_inst_t* inst, uint8_t seq_number,
                             t1_rblock_ack_t ack_code) {
  const t1_block_prm_t *p_prev = &inst->tx_prev_block_prm;

  if(inst->fsm_state == t1_st_wait_response) {
    switch(ack_code) {
      case t1_rblock_ack_ok:
        if(p_prev->block_type == t1_block_i && p_prev->iblock_prm.more_data &&
           seq_number != inst->tx_last_seq_number) {
          tx_fifo_remove_last_block(inst);
          return send_block_if_available(inst);
        }
        break;

      case t1_rblock_ack_err_edc:
      case t1_rblock_ack_err_other:
        // Flag block corruption because it was reported by card, so attempts
        // counter will not be re-initialized.
        inst->rx_bad_block = true;
        if(inst->tx_attempts + 1 < DELIVERY_ATTEMPTS) { // Resend block
          ++inst->tx_attempts;
          return resend_prev_block(inst);
        } else { // Resynchronization
          inst->tx_attempts = 0;
          inst->fsm_state = t1_st_resync;
          return send_sblock(inst, t1_sblock_cmd_resynch, false, -1);
        }
        break;
    }
  }
  return handle_bad_block(inst, t1_block_r, t1_rblock_ack_err_other);
}

/**
 * Increases response timeout for current transaction
 * @param inst  protocol instance
 * @param mult  multiplier
 */
static inline void increase_response_timeout(t1_inst_t* inst, uint8_t mult) {
  if(mult) {
    inst->tmr_response_timeout *= mult;
    if(inst->tmr_response_timeout > inst->config[t1_cfg_tm_response_max]) {
      inst->tmr_response_timeout = inst->config[t1_cfg_tm_response_max];
    }
  }
}

/**
 * Handles received S-block
 * @param inst         protocol instance
 * @param command      R-block parmeters
 * @param is_response  flag indicating that this is a response
 * @param inf_byte     INF byte, -1 if absent
 * @return             event or empty event with event_t::code = t1_ev_none
 */
static event_t handle_sblock(t1_inst_t* inst, t1_sblock_cmd_t command,
                            bool is_response, int16_t inf_byte) {
  if(inst->fsm_state != t1_st_resync) {
    switch(command) {
      case t1_sblock_cmd_ifs:
        if(is_response) {
          inst->tmr_response_timeout = 0U;
          event_t ev = send_block_if_available(inst);
          return is_error(ev) ? ev : event(t1_ev_connect);
        } else if(inf_byte >= IFS_MIN && inf_byte <= IFS_MAX) {
          inst->config[t1_cfg_ifsc] = inf_byte;
          return send_sblock(inst, t1_sblock_cmd_ifs, true, -1);
        }
        break;

      case t1_sblock_cmd_abort:
        return event(t1_ev_err_sc_abort);

      case t1_sblock_cmd_wtx:
        if(!is_response && inf_byte > 0) {
          event_t ev = send_sblock(inst, t1_sblock_cmd_wtx, true, -1);
          // Increase response time at least twice if the card is asking for it
          increase_response_timeout(inst, inf_byte < 2 ? 2 : inf_byte);
          return ev;
        }
        break;

      default:
        break;
    }
  } else { // Resynchronization
    if(command == t1_sblock_cmd_resynch && is_response) {
      // Reset protocol state and retry last I-block if available
      inst->tx_seq_number = 0;
      inst->tx_last_seq_number = 0;
      inst->rx_seq_number = 0;
      inst->config[t1_cfg_ifsc] = ext_config[t1_cfg_ifsc].def;
      inst->tx_prev_block_prm.block_type = t1_block_unkn;
      return send_block_if_available(inst);
    }
  }
  return handle_bad_block(inst, t1_block_s, t1_rblock_ack_err_other);
}

/**
 * Handles received T=1 block
 * @param inst   protocol instance
 * @param p_prm  pointer to structure with block parameters
 * @param inf    INF - information field, length is defined in p_prm::inf_len
 * @return       event or empty event with event_t::code = t1_ev_none
 */
static event_t handle_block(t1_inst_t* inst, t1_block_prm_t* p_prm,
                            const uint8_t* inf) {
  switch(p_prm->block_type) {
    case t1_block_i:
      return handle_iblock(inst, p_prm->iblock_prm.seq_number,
                           p_prm->iblock_prm.more_data, inf, p_prm->inf_len);

    case t1_block_r:
      if(p_prm->inf_len == 0) {
        return handle_rblock(inst, p_prm->rblock_prm.seq_number,
                             p_prm->rblock_prm.ack_code);
      }
      return handle_bad_block(inst, t1_block_r, t1_rblock_ack_err_other);

    case t1_block_s:
      return handle_sblock(inst, p_prm->sblock_prm.command,
                           p_prm->sblock_prm.is_response,
                           p_prm->sblock_prm.inf_byte);

    default:
      return handle_bad_block(inst, t1_block_unkn, t1_rblock_ack_err_other);
  }
  return event_none;
}

/**
 * Decodes PCB byte
 * @param p_prm  pointer to structure filled with block parameters
 * @param pcb    value of PCB byte
 */
static inline void decode_pcb(t1_block_prm_t* p_prm, uint8_t pcb) {
  p_prm->inf_len = 0;

  switch(pcb & PCB_MARKER_MASK) {
    case RB_MARKER: // R-block
      p_prm->block_type = t1_block_r;
      p_prm->rblock_prm.seq_number = (pcb & RB_NS_BIT) ? 1 : 0;
      p_prm->rblock_prm.ack_code = (t1_rblock_ack_t)(pcb & RB_ACK_MASK);
      break;

    case SB_MARKER: // S-block
      p_prm->block_type = t1_block_s;
      p_prm->sblock_prm.is_response = (pcb & SB_RESP_BIT) ? true : false;
      p_prm->sblock_prm.command = (t1_sblock_cmd_t)(pcb & SB_CMD_MASK);
      p_prm->sblock_prm.inf_byte = -1;
      break;

    default: // I-block
      p_prm->block_type = t1_block_i;
      p_prm->iblock_prm.more_data = (pcb & IB_M_BIT) ? true : false;
      p_prm->iblock_prm.seq_number = (pcb & IB_NS_BIT) ? 1 : 0;
      break;
  }
}

/**
 * Checks error detection code in received block
 * @param inst  protocol instance
 * @return      true if EDC is correct
 */
static bool check_rx_block_edc(const t1_inst_t* inst) {
  if(inst->rx_buf_idx >= prologue_size + edc_size(inst)) {
    uint8_t edc_buf[MAX_EDC_LEN];
    size_t checked_size = inst->rx_buf_idx - edc_size(inst);
    size_t res_size = calc_edc(inst, inst->rx_buf, checked_size,
                               edc_buf, sizeof(edc_buf));
    if(res_size) {
      const uint8_t* p_edc = inst->rx_buf + checked_size;
      for(int i = 0; i < res_size; i++) {
        if(edc_buf[i] != *p_edc++) {
          return false;
        }
      }
      return true;
    }
  }
  return false;
}

/**
 * Handles received T=1 data
 * @param inst       protocol instance
 * @param buf        buffer holding received bytes
 * @param len        number of bytes received
 * @return           event code in case of event or t1_ev_none
 */
static event_t handle_t1_data(t1_inst_t* inst, const uint8_t* buf, size_t len) {
  event_t ev = event_none;
  const uint8_t* p_byte = buf;

  for(size_t i = 0; i < len; i++, p_byte++) {
    // Store received byte in receive buffer
    if(inst->rx_buf_idx < T1_RX_BUF_SIZE) {
      inst->rx_buf[inst->rx_buf_idx++] = *p_byte;
    } else {
      ev = handle_bad_block(inst, t1_block_unkn, t1_rblock_ack_err_other);
      reset_rx(inst);
      return ev;
    }

    // Handle received byte
    switch(inst->rx_state) {
      case t1_rxs_skip:
        if(inst->rx_expected_bytes < 0) {
          inst->rx_expected_bytes = inst->config[t1_cfg_rx_skip_bytes];
        }
        if(inst->rx_expected_bytes && inst->rx_buf_idx) {
          --inst->rx_buf_idx; // Remove current byte from buffer
          --inst->rx_expected_bytes;
        } else {
          inst->rx_state = t1_rxs_pcb; // Skipping NAD byte
        }
        break;

      case t1_rxs_nad:
        inst->rx_state = t1_rxs_pcb; // Just skip NAD byte
        break;

      case t1_rxs_pcb:
        decode_pcb(&inst->rx_block_prm, *p_byte);
        inst->rx_state = t1_rxs_len;
        break;

      case t1_rxs_len:
        if(*p_byte == 0) { // INF is absent
          inst->rx_state = t1_rxs_edc;
          inst->rx_expected_bytes = edc_size(inst);
        } else if(*p_byte <= T1_MAX_LEN_VALUE) { // INF is present
          inst->rx_block_prm.inf_len = *p_byte;
          inst->rx_expected_bytes = *p_byte;
          inst->rx_state = t1_rxs_inf;
        } else { // Unsupported format
          ev = handle_bad_block(inst, t1_block_unkn, t1_rblock_ack_err_other);
          reset_rx(inst);
        }
        break;

      case t1_rxs_inf:
        if(--inst->rx_expected_bytes == 0) {
          inst->rx_state = t1_rxs_edc;
          inst->rx_expected_bytes = edc_size(inst);
        }
        break;

      case t1_rxs_edc:
        if(--inst->rx_expected_bytes == 0) {
          if(check_rx_block_edc(inst)) {
            // Fill single INF byte for S-block
            t1_block_prm_t* p_prm = &inst->rx_block_prm;
            if(p_prm->block_type == t1_block_s && p_prm->inf_len) {
              p_prm->sblock_prm.inf_byte = inst->rx_buf[prologue_size];
            }
            inst->rx_bad_block = false;
            ev = handle_block(inst, p_prm, inst->rx_buf + prologue_size);
            if(!inst->rx_bad_block && inst->fsm_state != t1_st_resync) {
              // Reset attempts counter if block is not flagged as bad
              inst->tx_attempts = 0;
            }
          } else {
            ev = handle_bad_block(inst, t1_block_unkn, t1_rblock_ack_err_edc);
          }
          reset_rx(inst);
        }
        break;
    }
  }
  return ev;
}

void t1_serial_in(t1_inst_t* inst, const uint8_t* buf, size_t len) {
  if(inst && buf && len && inst->fsm_state != t1_st_error) {
    event_list_t events = { .len = 0U };

    // Handle received data
    switch(inst->fsm_state) {
      case t1_st_wait_atr:
        inst->tmr_interbyte_timeout = inst->config[t1_cfg_tm_interbyte];
        event_add(&events, handle_atr_data(inst, buf, len));
        break;

      case t1_st_pps_exchange:
        inst->tmr_interbyte_timeout = inst->config[t1_cfg_tm_interbyte];
        handle_pps_data(inst, buf, len, &events);
        break;

      case t1_st_ifsd_setup:
      case t1_st_wait_response:
      case t1_st_resync:
        inst->tmr_interbyte_timeout = inst->config[t1_cfg_tm_interbyte];
        event_add(&events, handle_t1_data(inst, buf, len));
        break;

      default:
        break;
    }
    // Call event handler straight before returning
    handle_events(inst, &events);
  }
}

bool t1_transmit_apdu(t1_inst_t* inst, const uint8_t* apdu, size_t len) {
  if(inst && apdu && len && inst->fsm_state != t1_st_error) {
    if(push_iblock_chain(inst, apdu, len)) {
      if(inst->fsm_state == t1_st_idle) {
        event_t ev = tx_fifo_send_last_block(inst);
        inst->fsm_state = t1_st_wait_response;
        handle_event(inst, ev); // Call event handler straight before returning
        return !is_error(ev);
      }
      return true;
    }
  }
  return false;
}

bool t1_is_error_event(t1_ev_code_t ev_code) {
  return ev_code >= t1_ev_err_internal;
}

bool t1_has_error(const t1_inst_t* inst) {
  return inst->fsm_state == t1_st_error;
}
