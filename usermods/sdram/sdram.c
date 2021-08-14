#include <assert.h>
#include <string.h>
#include "py/obj.h"
#include "py/runtime.h"
#include "py/builtin.h"

// works only together with udisplay module, for now...
#include "stm32469i_discovery_sdram.h"

#define PREALLOCATED_SDRAM_PTR 0xC02EE000 // 0xC0000000+480*800*4*2
#define PREALLOCATED_SDRAM_SIZE 0x100000  // ~1 MB

#define SDRAM_START_ADDRESS ((size_t)0xC03EE000)
#define SDRAM_END_ADDRESS   ((size_t)0xC1000000)

typedef struct _mp_obj_sdram_ramdevice_t {
    mp_obj_base_t base;
    size_t start;
    size_t len;
    size_t block_size;
} mp_obj_sdram_ramdevice_t;

/****************************** RAMDevice class ******************************/

STATIC mp_obj_t sdram_ramdevice_make_new(const mp_obj_type_t *type, 
                                        size_t n_args, size_t n_kw, 
                                        const mp_obj_t *args) {
    mp_arg_check_num(n_args, n_kw, 0, 3, false);
    mp_obj_sdram_ramdevice_t *o = m_new_obj(mp_obj_sdram_ramdevice_t);
    o->base.type = type;
    o->start = SDRAM_START_ADDRESS;
    o->len = SDRAM_END_ADDRESS-SDRAM_START_ADDRESS;
    if(n_args+n_kw > 0){
        o->block_size = mp_obj_get_int(args[0]);
    }else{
        o->block_size = 512;
    }
    return MP_OBJ_FROM_PTR(o);
}

// meh... not sure we need copy
STATIC mp_obj_t sdram_ramdevice_copy(mp_obj_t self_in) {
    mp_obj_sdram_ramdevice_t *o = m_new_obj(mp_obj_sdram_ramdevice_t);
    mp_obj_sdram_ramdevice_t *self = MP_OBJ_TO_PTR(self_in);
    o->base.type = self->base.type;
    return MP_OBJ_FROM_PTR(o);
}

STATIC mp_obj_t sdram_ramdevice_readblocks(mp_obj_t self_in, 
                                           mp_obj_t block_num, 
                                           mp_obj_t buf) {
    mp_obj_sdram_ramdevice_t *self = MP_OBJ_TO_PTR(self_in);
    mp_buffer_info_t buffer;
    mp_get_buffer_raise(buf, &buffer, MP_BUFFER_WRITE);
    size_t start = self->start + mp_obj_get_int(block_num)*self->block_size;
    if(start+buffer.len >= SDRAM_END_ADDRESS){
        mp_raise_ValueError("Outer space...");
        return mp_const_none;
    }
    memcpy(buffer.buf, (uint8_t *)start, buffer.len);
    return mp_const_none;
}

STATIC mp_obj_t sdram_ramdevice_writeblocks(mp_obj_t self_in, 
                                           mp_obj_t block_num, 
                                           mp_obj_t buf) {
    mp_obj_sdram_ramdevice_t *self = MP_OBJ_TO_PTR(self_in);
    mp_buffer_info_t buffer;
    mp_get_buffer_raise(buf, &buffer, MP_BUFFER_READ);
    size_t start = (self->start + mp_obj_get_int(block_num)*self->block_size);
    if(start+buffer.len >= SDRAM_END_ADDRESS){
        mp_raise_ValueError("Outer space...");
        return mp_const_none;
    }
    memcpy((uint8_t *)start, buffer.buf, buffer.len);
    return mp_const_none;
}

STATIC mp_obj_t sdram_ramdevice_ioctl(mp_obj_t self_in, 
                                           mp_obj_t op, 
                                           mp_obj_t arg) {
    mp_obj_sdram_ramdevice_t *self = MP_OBJ_TO_PTR(self_in);
    mp_int_t op_int = mp_obj_get_int(op);
    if(op_int == 4){
        return mp_obj_new_int(self->len / self->block_size);
    }else if(op_int == 5){
        return mp_obj_new_int(self->block_size);
    }
    return mp_const_none;
}

STATIC MP_DEFINE_CONST_FUN_OBJ_3(sdram_ramdevice_readblocks_obj, sdram_ramdevice_readblocks);
STATIC MP_DEFINE_CONST_FUN_OBJ_3(sdram_ramdevice_writeblocks_obj, sdram_ramdevice_writeblocks);
STATIC MP_DEFINE_CONST_FUN_OBJ_3(sdram_ramdevice_ioctl_obj, sdram_ramdevice_ioctl);
STATIC MP_DEFINE_CONST_FUN_OBJ_1(sdram_ramdevice_copy_obj, sdram_ramdevice_copy);

STATIC const mp_rom_map_elem_t sdram_ramdevice_dict_table[] = {
    { MP_ROM_QSTR(MP_QSTR_readblocks), MP_ROM_PTR(&sdram_ramdevice_readblocks_obj) },
    { MP_ROM_QSTR(MP_QSTR_writeblocks), MP_ROM_PTR(&sdram_ramdevice_writeblocks_obj) },
    { MP_ROM_QSTR(MP_QSTR_ioctl), MP_ROM_PTR(&sdram_ramdevice_ioctl_obj) },
    { MP_ROM_QSTR(MP_QSTR_copy), MP_ROM_PTR(&sdram_ramdevice_copy_obj) },
};

STATIC MP_DEFINE_CONST_DICT(sdram_ramdevice_dict, sdram_ramdevice_dict_table);

STATIC const mp_obj_type_t sdram_ramdevice_type = {
    { &mp_type_type },
    .name = MP_QSTR_ramdevice,
    .make_new = sdram_ramdevice_make_new,
    .locals_dict = (void*)&sdram_ramdevice_dict,
};

STATIC mp_obj_t sdram_init() {
    BSP_SDRAM_Init();
    return mp_const_none;
}
STATIC MP_DEFINE_CONST_FUN_OBJ_0(sdram_init_obj, sdram_init);

/***************** 1MB preallocated memory ***************/
STATIC mp_obj_t sdram_preallocated_ptr() {
    return mp_obj_new_int_from_ull(PREALLOCATED_SDRAM_PTR);
}
STATIC MP_DEFINE_CONST_FUN_OBJ_0(sdram_preallocated_ptr_obj, sdram_preallocated_ptr);

STATIC mp_obj_t sdram_preallocated_size() {
    return mp_obj_new_int_from_ull(PREALLOCATED_SDRAM_SIZE);
}
STATIC MP_DEFINE_CONST_FUN_OBJ_0(sdram_preallocated_size_obj, sdram_preallocated_size);

/****************************** MODULE ******************************/

STATIC const mp_rom_map_elem_t sdram_module_globals_table[] = {
    { MP_ROM_QSTR(MP_QSTR___name__), MP_ROM_QSTR(MP_QSTR_sdram) },
    { MP_ROM_QSTR(MP_QSTR_RAMDevice), MP_ROM_PTR(&sdram_ramdevice_type) },
    { MP_ROM_QSTR(MP_QSTR_init), MP_ROM_PTR(&sdram_init_obj) },

    { MP_ROM_QSTR(MP_QSTR_preallocated_ptr), MP_ROM_PTR(&sdram_preallocated_ptr_obj) },
    { MP_ROM_QSTR(MP_QSTR_preallocated_size), MP_ROM_PTR(&sdram_preallocated_size_obj) },
};

STATIC MP_DEFINE_CONST_DICT(sdram_module_globals, sdram_module_globals_table);

const mp_obj_module_t sdram_user_cmodule = {
    .base = { &mp_type_module },
    .globals = (mp_obj_dict_t*)&sdram_module_globals,
};

MP_REGISTER_MODULE(MP_QSTR_sdram, sdram_user_cmodule, MODULE_SDRAM_ENABLED);
