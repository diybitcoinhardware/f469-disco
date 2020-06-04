/**
 * @file   fifo_buf.h
 * @brief  FIFO buffer implementation, header-only module
 * @author Mike Tolkachev <mstolkachev@gmail.com>
 */

#ifndef FIFO_BUF_H
#define FIFO_BUF_H

#include <stddef.h>
#include <stdint.h>

/// FIFO buffer instance
typedef struct {
  /// Pointer to memory buffer
  uint8_t* buf;
  /// Head index
  size_t head;
  /// Tail index
  size_t tail;
  /// Number of elements in memory buffer (capacity)
  size_t nelem;
} fifo_buf_inst_t;

#ifdef FIFO_BUF_IMPLEMENT

/**
 * Constructs a new fifo object
 * @param fifo   pointer to FIFO instance structure, contents are "don't-care"
 * @param buf    memory buffer used to store elements of FIFO buffer
 * @param nelem  number of elements (bytes) in FIFO buffer
 */
static inline void fifo_init(fifo_buf_inst_t* fifo, uint8_t* buf, size_t nelem) {
  fifo->buf = buf;
  fifo->head = 0;
  fifo->tail = 0;
  fifo->nelem = nelem;
}

/**
 * Empties FIFO buffer
 * @param fifo  FIFO buffer instance
 */
static inline void fifo_clear(fifo_buf_inst_t* fifo) {
  fifo->head = 0;
  fifo->tail = 0;
}

/**
 * Returns free space in FIFO buffer
 * @param fifo  FIFO buffer instance
 * @return      number of free elements
 */
static inline size_t fifo_nfree(const fifo_buf_inst_t* fifo) {
    return (fifo->head >= fifo->tail) ?
      fifo->nelem - fifo->head + fifo->tail - 1 :
      fifo->tail - fifo->head - 1;
}

/**
 * Returns occupied space in FIFO buffer
 * @param fifo  FIFO buffer instance
 * @return      number of used elements
 */
static inline size_t fifo_nused(const fifo_buf_inst_t* fifo) {
    return (fifo->head >= fifo->tail) ?
      fifo->head - fifo->tail :
      fifo->nelem - fifo->tail + fifo->head;
}

/**
 * Pushes one byte of data into FIFO buffer
 * @param fifo  FIFO buffer instance
 * @param byte  byte
 */
static inline void fifo_push(fifo_buf_inst_t* fifo, uint8_t byte) {
  fifo->buf[fifo->head] = byte;
  fifo->head = (fifo->head >= fifo->nelem - 1) ? 0 : fifo->head + 1;
}

/**
 * Pushes contents of buffer into FIFO buffer
 * @param fifo  FIFO buffer instance
 * @param buf   source buffer
 * @param len   number of bytes in input buffer
 */
static inline void fifo_push_buf(fifo_buf_inst_t* fifo, const uint8_t* buf,
                                 size_t len) {
  while(len--) {
    fifo_push(fifo, *buf++);
  }
}

/**
 * Pops one byte of data from FIFO buffer
 * @param fifo  FIFO buffer instance
 * @return      byte
 */
static inline uint8_t fifo_pop(fifo_buf_inst_t* fifo) {
  uint8_t byte = fifo->buf[fifo->tail];
  fifo->tail = (fifo->tail >= fifo->nelem - 1) ? 0 : fifo->tail + 1;
  return byte;
}

/**
 * Pops a number of bytes from FIFO buffer
 * @param fifo      FIFO buffer instance
 * @param dst_buf   destination buffer
 * @param dst_size  size of destination buffer in bytes
 * @param nbytes    number of bytes to pop
 */
static inline void fifo_pop_buf(fifo_buf_inst_t* fifo, uint8_t* dst_buf,
                                size_t dst_size, size_t nbytes) {
  size_t len = (nbytes <= dst_size) ? nbytes : dst_size;
  while(len--) {
    *dst_buf++ = fifo_pop(fifo);
  }
}

/**
 * Returns current read index
 *
 * Use this function to initialize read index for fifo_read() and
 * fifo_read_buf().
 * @param fifo  FIFO buffer instance
 * @return      current read index
 */
static inline size_t fifo_get_read_idx(const fifo_buf_inst_t* fifo) {
  return fifo->tail;
}

/**
 * Returns next byte while not removing it from FIFO buffer
 *
 * Before first call of fifo_read() a temporary variable holding current read
 * index needs to be initialized by calling fifo_get_read_idx(). Then each
 * subsequent call of fifo_read() will update read index and return the next
 * byte from FIFO.
 * @param fifo        FIFO buffer instance
 * @param p_read_idx  pointer to current read index (see description)
 * @return            byte
 */
static inline uint8_t fifo_read(const fifo_buf_inst_t* fifo,
                                size_t* p_read_idx) {
  uint8_t byte = fifo->buf[*p_read_idx];
  *p_read_idx = (*p_read_idx >= fifo->nelem - 1) ? 0 : *p_read_idx + 1;
  return byte;
}

/**
 * Reads data while not removing it from FIFO buffer
 * @param fifo        FIFO buffer instance
 * @param p_read_idx  pointer to current read index, see fifo_read()
 * @param dst_buf     destination buffer
 * @param dst_size    size of destination buffer in bytes
 * @param nbytes      number of bytes to pop
 */
static inline void fifo_read_buf(const fifo_buf_inst_t* fifo,
                                 size_t* p_read_idx, uint8_t* dst_buf,
                                 size_t dst_size, size_t nbytes) {
  size_t len = (nbytes <= dst_size) ? nbytes : dst_size;
  while(len--) {
    *dst_buf++ = fifo_read(fifo, p_read_idx);
  }
}

/**
 * Removes byte(s) from FIFO buffer
 * @param fifo    FIFO buffer instance
 * @param nbytes  number of bytes to remove
 */
static inline void fifo_remove(fifo_buf_inst_t* fifo, size_t nbytes) {
  fifo->tail += nbytes;
  if(fifo->tail >= fifo->nelem) {
    fifo->tail %= fifo->nelem;
  }
}

#endif // FIFO_BUF_IMPLEMENT

#endif // FIFO_BUF_H
