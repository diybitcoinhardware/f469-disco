/**
 * @file       reader.h
 * @brief      MicroPython uscard module: Reader class
 * @author     Mike Tolkachev <contact@miketolkachev.dev>
 * @copyright  Copyright 2020 Crypto Advance GmbH. All rights reserved.
 */

#ifndef READER_H_INCLUDED
/// Avoids multiple inclusion of this file
#define READER_H_INCLUDED

#include "py/obj.h"

/// Reader class type
extern const mp_obj_type_t scard_Reader_type;

/**
 * Deletes a smart card connection
 *
 * Called from CardConnection.close(), not exposed to Python
 *
 * @param self        instance of Reader class
 * @param connection  instance of CardConnection class
 */
extern void reader_deleteConnection(mp_obj_t* self_in, mp_obj_t* connection);

#endif // READER_H_INCLUDED
