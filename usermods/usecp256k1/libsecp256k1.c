#include <assert.h>
#include <string.h>
#include <stdlib.h>
#include "include/secp256k1.h"
#include "include/secp256k1_preallocated.h"
#include "py/obj.h"
#include "py/runtime.h"
#include "py/builtin.h"
#include "py/gc.h"

#define malloc(b) gc_alloc((b), false)
#define free gc_free

// global context
#define PREALLOCATED_CTX_SIZE 880 // 440 for 32-bit. FIXME: autodetect

STATIC unsigned char preallocated_ctx[PREALLOCATED_CTX_SIZE];
STATIC secp256k1_context * ctx = NULL;

void maybe_init_ctx(){
    if(ctx != NULL){
        return;
    }
    // ctx = secp256k1_context_create(SECP256K1_CONTEXT_VERIFY | SECP256K1_CONTEXT_SIGN);
    ctx = secp256k1_context_preallocated_create((void *)preallocated_ctx, SECP256K1_CONTEXT_VERIFY | SECP256K1_CONTEXT_SIGN);
}

// create public key from private key
STATIC mp_obj_t usecp256k1_ec_pubkey_create(const mp_obj_t arg){
    maybe_init_ctx();
    mp_buffer_info_t secretbuf;
    mp_get_buffer_raise(arg, &secretbuf, MP_BUFFER_READ);
    if(secretbuf.len != 32){
        mp_raise_ValueError("Private key should be 32 bytes long");
        return mp_const_none;
    }
    secp256k1_pubkey pubkey;
    int res = secp256k1_ec_pubkey_create(ctx, &pubkey, secretbuf.buf);
    if(!res){
        mp_raise_ValueError("Invalid private key");
        return mp_const_none;
    }
    vstr_t vstr;
    vstr_init_len(&vstr, 64);
    memcpy((byte*)vstr.buf, pubkey.data, 64);

    return mp_obj_new_str_from_vstr(&mp_type_bytes, &vstr);
}

STATIC MP_DEFINE_CONST_FUN_OBJ_1(usecp256k1_ec_pubkey_create_obj, usecp256k1_ec_pubkey_create);

// parse sec-encoded public key
STATIC mp_obj_t usecp256k1_ec_pubkey_parse(const mp_obj_t arg){
    maybe_init_ctx();
    mp_buffer_info_t secbuf;
    mp_get_buffer_raise(arg, &secbuf, MP_BUFFER_READ);
    if(secbuf.len != 33 && secbuf.len != 65){
        mp_raise_ValueError("Serialized pubkey should be 33 or 65 bytes long");
        return mp_const_none;
    }
    byte * buf = (byte*)secbuf.buf;
    switch(secbuf.len){
        case 33:
            if(buf[0] != 0x02 && buf[0] != 0x03){
                mp_raise_ValueError("Compressed pubkey should start with 0x02 or 0x03");
                return mp_const_none;
            }
            break;
        case 65:
            if(buf[0] != 0x04){
                mp_raise_ValueError("Uncompressed pubkey should start with 0x04");
                return mp_const_none;
            }
            break;
    }
    secp256k1_pubkey pubkey;
    int res = secp256k1_ec_pubkey_parse(ctx, &pubkey, secbuf.buf, secbuf.len);
    if(!res){
        mp_raise_ValueError("Failed parsing public key");
        return mp_const_none;
    }
    vstr_t vstr;
    vstr_init_len(&vstr, 64);
    memcpy((byte*)vstr.buf, pubkey.data, 64);

    return mp_obj_new_str_from_vstr(&mp_type_bytes, &vstr);
}

STATIC MP_DEFINE_CONST_FUN_OBJ_1(usecp256k1_ec_pubkey_parse_obj, usecp256k1_ec_pubkey_parse);

// serialize public key
STATIC mp_obj_t usecp256k1_ec_pubkey_serialize(mp_uint_t n_args, const mp_obj_t *args){
    maybe_init_ctx();
    mp_buffer_info_t pubbuf;
    mp_get_buffer_raise(args[0], &pubbuf, MP_BUFFER_READ);
    if(pubbuf.len != 64){
        mp_raise_ValueError("Pubkey should be 64 bytes long");
        return mp_const_none;
    }
    secp256k1_pubkey pubkey;
    memcpy(pubkey.data, pubbuf.buf, 64);
    mp_int_t flag = SECP256K1_EC_COMPRESSED;
    if(n_args > 1){
        flag = mp_obj_get_int(args[1]);
    }
    byte out[65];
    size_t len = 65;
    int res = secp256k1_ec_pubkey_serialize(ctx, out, &len, &pubkey, flag);
    vstr_t vstr;
    vstr_init_len(&vstr, len);
    memcpy((byte*)vstr.buf, out, len);
    return mp_obj_new_str_from_vstr(&mp_type_bytes, &vstr);
}

STATIC MP_DEFINE_CONST_FUN_OBJ_VAR(usecp256k1_ec_pubkey_serialize_obj, 1, usecp256k1_ec_pubkey_serialize);

// parse compact ecdsa signature
STATIC mp_obj_t usecp256k1_ecdsa_signature_parse_compact(const mp_obj_t arg){
    maybe_init_ctx();
    mp_buffer_info_t buf;
    mp_get_buffer_raise(arg, &buf, MP_BUFFER_READ);
    if(buf.len != 64){
        mp_raise_ValueError("Compact signature should be 64 bytes long");
        return mp_const_none;
    }
    secp256k1_ecdsa_signature sig;
    int res = secp256k1_ecdsa_signature_parse_compact(ctx, &sig, buf.buf);
    if(!res){
        mp_raise_ValueError("Failed parsing compact signature");
        return mp_const_none;
    }
    vstr_t vstr;
    vstr_init_len(&vstr, 64);
    memcpy((byte*)vstr.buf, sig.data, 64);

    return mp_obj_new_str_from_vstr(&mp_type_bytes, &vstr);
}

STATIC MP_DEFINE_CONST_FUN_OBJ_1(usecp256k1_ecdsa_signature_parse_compact_obj, usecp256k1_ecdsa_signature_parse_compact);

// parse der ecdsa signature
STATIC mp_obj_t usecp256k1_ecdsa_signature_parse_der(const mp_obj_t arg){
    maybe_init_ctx();
    mp_buffer_info_t buf;
    mp_get_buffer_raise(arg, &buf, MP_BUFFER_READ);
    secp256k1_ecdsa_signature sig;
    int res = secp256k1_ecdsa_signature_parse_der(ctx, &sig, buf.buf, buf.len);
    if(!res){
        mp_raise_ValueError("Failed parsing der signature");
        return mp_const_none;
    }
    vstr_t vstr;
    vstr_init_len(&vstr, 64);
    memcpy((byte*)vstr.buf, sig.data, 64);

    return mp_obj_new_str_from_vstr(&mp_type_bytes, &vstr);
}

STATIC MP_DEFINE_CONST_FUN_OBJ_1(usecp256k1_ecdsa_signature_parse_der_obj, usecp256k1_ecdsa_signature_parse_der);

// serialize der ecdsa signature
STATIC mp_obj_t usecp256k1_ecdsa_signature_serialize_der(const mp_obj_t arg){
    maybe_init_ctx();
    mp_buffer_info_t buf;
    mp_get_buffer_raise(arg, &buf, MP_BUFFER_READ);
    if(buf.len != 64){
        mp_raise_ValueError("Signature should be 64 bytes long");
        return mp_const_none;
    }
    secp256k1_ecdsa_signature sig;
    memcpy(sig.data, buf.buf, 64);
    byte out[78];
    size_t len = 78;
    int res = secp256k1_ecdsa_signature_serialize_der(ctx, out, &len, &sig);
    if(!res){
        mp_raise_ValueError("Failed serializing der signature");
        return mp_const_none;
    }
    vstr_t vstr;
    vstr_init_len(&vstr, len);
    memcpy((byte*)vstr.buf, out, len);

    return mp_obj_new_str_from_vstr(&mp_type_bytes, &vstr);
}

STATIC MP_DEFINE_CONST_FUN_OBJ_1(usecp256k1_ecdsa_signature_serialize_der_obj, usecp256k1_ecdsa_signature_serialize_der);

// serialize der ecdsa signature
STATIC mp_obj_t usecp256k1_ecdsa_signature_serialize_compact(const mp_obj_t arg){
    maybe_init_ctx();
    mp_buffer_info_t buf;
    mp_get_buffer_raise(arg, &buf, MP_BUFFER_READ);
    if(buf.len != 64){
        mp_raise_ValueError("Signature should be 64 bytes long");
        return mp_const_none;
    }
    secp256k1_ecdsa_signature sig;
    memcpy(sig.data, buf.buf, 64);
    vstr_t vstr;
    vstr_init_len(&vstr, 64);
    secp256k1_ecdsa_signature_serialize_compact(ctx, (byte*)vstr.buf, &sig);
    return mp_obj_new_str_from_vstr(&mp_type_bytes, &vstr);
}

STATIC MP_DEFINE_CONST_FUN_OBJ_1(usecp256k1_ecdsa_signature_serialize_compact_obj, usecp256k1_ecdsa_signature_serialize_compact);

// serialize der ecdsa signature
STATIC mp_obj_t usecp256k1_ecdsa_verify(const mp_obj_t sigarg, const mp_obj_t msgarg, const mp_obj_t pubkeyarg){
    maybe_init_ctx();
    mp_buffer_info_t buf;
    mp_get_buffer_raise(sigarg, &buf, MP_BUFFER_READ);
    if(buf.len != 64){
        mp_raise_ValueError("Signature should be 64 bytes long");
        return mp_const_none;
    }
    secp256k1_ecdsa_signature sig;
    memcpy(sig.data, buf.buf, 64);

    mp_get_buffer_raise(msgarg, &buf, MP_BUFFER_READ);
    if(buf.len != 32){
        mp_raise_ValueError("Message should be 32 bytes long");
        return mp_const_none;
    }
    byte msg[32];
    memcpy(msg, buf.buf, 32);

    mp_get_buffer_raise(pubkeyarg, &buf, MP_BUFFER_READ);
    if(buf.len != 64){
        mp_raise_ValueError("Public key should be 64 bytes long");
        return mp_const_none;
    }
    secp256k1_pubkey pub;
    memcpy(pub.data, buf.buf, 64);

    int res = secp256k1_ecdsa_verify(ctx, &sig, msg, &pub);
    if(res){
        return mp_const_true;
    }
    return mp_const_false;
}

STATIC MP_DEFINE_CONST_FUN_OBJ_3(usecp256k1_ecdsa_verify_obj, usecp256k1_ecdsa_verify);

// normalize ecdsa signature
STATIC mp_obj_t usecp256k1_ecdsa_signature_normalize(const mp_obj_t arg){
    maybe_init_ctx();
    mp_buffer_info_t buf;
    mp_get_buffer_raise(arg, &buf, MP_BUFFER_READ);
    if(buf.len != 64){
        mp_raise_ValueError("Signature should be 64 bytes long");
        return mp_const_none;
    }
    secp256k1_ecdsa_signature sig;
    secp256k1_ecdsa_signature sig2;
    memcpy(sig.data, buf.buf, 64);
    vstr_t vstr;
    vstr_init_len(&vstr, 64);
    secp256k1_ecdsa_signature_normalize(ctx, &sig2, &sig);
    memcpy(vstr.buf, sig2.data, 64);
    return mp_obj_new_str_from_vstr(&mp_type_bytes, &vstr);
}

STATIC MP_DEFINE_CONST_FUN_OBJ_1(usecp256k1_ecdsa_signature_normalize_obj, usecp256k1_ecdsa_signature_normalize);

// sign
STATIC mp_obj_t usecp256k1_ecdsa_sign(const mp_obj_t msgarg, const mp_obj_t secarg){
    maybe_init_ctx();
    mp_buffer_info_t msgbuf;
    mp_get_buffer_raise(msgarg, &msgbuf, MP_BUFFER_READ);
    if(msgbuf.len != 32){
        mp_raise_ValueError("Message should be 32 bytes long");
        return mp_const_none;
    }

    mp_buffer_info_t secbuf;
    mp_get_buffer_raise(secarg, &secbuf, MP_BUFFER_READ);
    if(secbuf.len != 32){
        mp_raise_ValueError("Secret key should be 32 bytes long");
        return mp_const_none;
    }

    secp256k1_ecdsa_signature sig;
    int res = secp256k1_ecdsa_sign(ctx, &sig, msgbuf.buf, secbuf.buf, NULL, NULL);
    if(!res){
        mp_raise_ValueError("Failed to sign");
        return mp_const_none;
    }

    vstr_t vstr;
    vstr_init_len(&vstr, 64);
    memcpy((byte*)vstr.buf, sig.data, 64);

    return mp_obj_new_str_from_vstr(&mp_type_bytes, &vstr);
}

STATIC MP_DEFINE_CONST_FUN_OBJ_2(usecp256k1_ecdsa_sign_obj, usecp256k1_ecdsa_sign);

// verify secret key
STATIC mp_obj_t usecp256k1_ec_seckey_verify(const mp_obj_t arg){
    maybe_init_ctx();
    mp_buffer_info_t buf;
    mp_get_buffer_raise(arg, &buf, MP_BUFFER_READ);
    if(buf.len != 32){
        mp_raise_ValueError("Private key should be 32 bytes long");
        return mp_const_none;
    }

    int res = secp256k1_ec_seckey_verify(ctx, buf.buf);
    if(res){
        return mp_const_true;
    }
    return mp_const_false;
}

STATIC MP_DEFINE_CONST_FUN_OBJ_1(usecp256k1_ec_seckey_verify_obj, usecp256k1_ec_seckey_verify);

// negate secret key in place
STATIC mp_obj_t usecp256k1_ec_privkey_negate(mp_obj_t arg){
    maybe_init_ctx();
    mp_buffer_info_t buf;
    mp_get_buffer_raise(arg, &buf, MP_BUFFER_READ);
    if(buf.len != 32){
        mp_raise_ValueError("Private key should be 32 bytes long");
        return mp_const_none;
    }

    int res = secp256k1_ec_privkey_negate(ctx, buf.buf);
    if(!res){ // never happens according to the API
        mp_raise_ValueError("Failed to negate the private key");
        return mp_const_none;
    }
    return mp_const_none;
}

STATIC MP_DEFINE_CONST_FUN_OBJ_1(usecp256k1_ec_privkey_negate_obj, usecp256k1_ec_privkey_negate);

// negate secret key in place
STATIC mp_obj_t usecp256k1_ec_pubkey_negate(mp_obj_t arg){
    maybe_init_ctx();
    mp_buffer_info_t buf;
    mp_get_buffer_raise(arg, &buf, MP_BUFFER_READ);
    if(buf.len != 64){
        mp_raise_ValueError("Publick key should be 64 bytes long");
        return mp_const_none;
    }

    int res = secp256k1_ec_pubkey_negate(ctx, buf.buf);
    if(!res){ // never happens according to the API
        mp_raise_ValueError("Failed to negate the public key");
        return mp_const_none;
    }
    return mp_const_none;
}

STATIC MP_DEFINE_CONST_FUN_OBJ_1(usecp256k1_ec_pubkey_negate_obj, usecp256k1_ec_pubkey_negate);

// tweak private key in place
STATIC mp_obj_t usecp256k1_ec_privkey_tweak_add(mp_obj_t privarg, const mp_obj_t tweakarg){
    maybe_init_ctx();
    mp_buffer_info_t privbuf;
    mp_get_buffer_raise(privarg, &privbuf, MP_BUFFER_READ);
    if(privbuf.len != 32){
        mp_raise_ValueError("Private key should be 32 bytes long");
        return mp_const_none;
    }

    mp_buffer_info_t tweakbuf;
    mp_get_buffer_raise(tweakarg, &tweakbuf, MP_BUFFER_READ);
    if(tweakbuf.len != 32){
        mp_raise_ValueError("Tweak should be 32 bytes long");
        return mp_const_none;
    }

    int res = secp256k1_ec_privkey_tweak_add(ctx, privbuf.buf, tweakbuf.buf);
    if(!res){ // never happens according to the API
        mp_raise_ValueError("Failed to tweak the private key");
        return mp_const_none;
    }
    return mp_const_none;
}

STATIC MP_DEFINE_CONST_FUN_OBJ_2(usecp256k1_ec_privkey_tweak_add_obj, usecp256k1_ec_privkey_tweak_add);

// tweak public key in place (add tweak * Generator)
STATIC mp_obj_t usecp256k1_ec_pubkey_tweak_add(mp_obj_t pubarg, const mp_obj_t tweakarg){
    maybe_init_ctx();
    mp_buffer_info_t pubbuf;
    mp_get_buffer_raise(pubarg, &pubbuf, MP_BUFFER_READ);
    if(pubbuf.len != 64){
        mp_raise_ValueError("Public key should be 64 bytes long");
        return mp_const_none;
    }
    secp256k1_pubkey pub;
    memcpy(pub.data, pubbuf.buf, 64);

    mp_buffer_info_t tweakbuf;
    mp_get_buffer_raise(tweakarg, &tweakbuf, MP_BUFFER_READ);
    if(tweakbuf.len != 32){
        mp_raise_ValueError("Tweak should be 32 bytes long");
        return mp_const_none;
    }

    int res = secp256k1_ec_pubkey_tweak_add(ctx, &pub, tweakbuf.buf);
    if(!res){ // never happens according to the API
        mp_raise_ValueError("Failed to tweak the public key");
        return mp_const_none;
    }
    memcpy(pubbuf.buf, pub.data, 64);
    return mp_const_none;
}

STATIC MP_DEFINE_CONST_FUN_OBJ_2(usecp256k1_ec_pubkey_tweak_add_obj, usecp256k1_ec_pubkey_tweak_add);

// tweak private key in place (multiply by tweak)
STATIC mp_obj_t usecp256k1_ec_privkey_tweak_mul(mp_obj_t privarg, const mp_obj_t tweakarg){
    maybe_init_ctx();
    mp_buffer_info_t privbuf;
    mp_get_buffer_raise(privarg, &privbuf, MP_BUFFER_READ);
    if(privbuf.len != 32){
        mp_raise_ValueError("Private key should be 32 bytes long");
        return mp_const_none;
    }

    mp_buffer_info_t tweakbuf;
    mp_get_buffer_raise(tweakarg, &tweakbuf, MP_BUFFER_READ);
    if(tweakbuf.len != 32){
        mp_raise_ValueError("Tweak should be 32 bytes long");
        return mp_const_none;
    }

    int res = secp256k1_ec_privkey_tweak_mul(ctx, privbuf.buf, tweakbuf.buf);
    if(!res){ // never happens according to the API
        mp_raise_ValueError("Failed to tweak the public key");
        return mp_const_none;
    }
    return mp_const_none;
}

STATIC MP_DEFINE_CONST_FUN_OBJ_2(usecp256k1_ec_privkey_tweak_mul_obj, usecp256k1_ec_privkey_tweak_mul);

// tweak public key in place (multiply by tweak)
STATIC mp_obj_t usecp256k1_ec_pubkey_tweak_mul(mp_obj_t pubarg, const mp_obj_t tweakarg){
    maybe_init_ctx();
    mp_buffer_info_t pubbuf;
    mp_get_buffer_raise(pubarg, &pubbuf, MP_BUFFER_READ);
    if(pubbuf.len != 64){
        mp_raise_ValueError("Public key should be 64 bytes long");
        return mp_const_none;
    }
    secp256k1_pubkey pub;
    memcpy(pub.data, pubbuf.buf, 64);

    mp_buffer_info_t tweakbuf;
    mp_get_buffer_raise(tweakarg, &tweakbuf, MP_BUFFER_READ);
    if(tweakbuf.len != 32){
        mp_raise_ValueError("Tweak should be 32 bytes long");
        return mp_const_none;
    }

    int res = secp256k1_ec_pubkey_tweak_mul(ctx, &pub, tweakbuf.buf);
    if(!res){ // never happens according to the API
        mp_raise_ValueError("Failed to tweak the public key");
        return mp_const_none;
    }
    memcpy(pubbuf.buf, pub.data, 64);
    return mp_const_none;
}

STATIC MP_DEFINE_CONST_FUN_OBJ_2(usecp256k1_ec_pubkey_tweak_mul_obj, usecp256k1_ec_pubkey_tweak_mul);

// adds public keys
STATIC mp_obj_t usecp256k1_ec_pubkey_combine(mp_uint_t n_args, const mp_obj_t *args){
    maybe_init_ctx();
    secp256k1_pubkey pubkey;
    secp256k1_pubkey ** pubkeys;
    pubkeys = (secp256k1_pubkey **)malloc(sizeof(secp256k1_pubkey*)*n_args);
    mp_buffer_info_t pubbuf;
    for(int i=0; i<n_args; i++){ // TODO: can be refactored to avoid allocation
        mp_get_buffer_raise(args[i], &pubbuf, MP_BUFFER_READ);
        if(pubbuf.len != 64){
            for(int j=0; j<i; j++){
                free(pubkeys[j]);
            }
            free(pubkeys);
            mp_raise_ValueError("All pubkeys should be 64 bytes long");
            return mp_const_none;
        }
        pubkeys[i] = (secp256k1_pubkey *)malloc(64);
        memcpy(pubkeys[i]->data, pubbuf.buf, 64);
    }
    int res = secp256k1_ec_pubkey_combine(ctx, &pubkey, (const secp256k1_pubkey *const *)pubkeys, n_args);
    vstr_t vstr;
    vstr_init_len(&vstr, 64);
    memcpy((byte*)vstr.buf, pubkey.data, 64);
    for(int i=0; i<n_args; i++){
        free(pubkeys[i]);
    }
    free(pubkeys);
    return mp_obj_new_str_from_vstr(&mp_type_bytes, &vstr);
}

STATIC MP_DEFINE_CONST_FUN_OBJ_VAR(usecp256k1_ec_pubkey_combine_obj, 2, usecp256k1_ec_pubkey_combine);

/****************************** MODULE ******************************/

STATIC const mp_rom_map_elem_t secp256k1_module_globals_table[] = {
    { MP_ROM_QSTR(MP_QSTR___name__), MP_ROM_QSTR(MP_QSTR_secp256k1) },
    { MP_ROM_QSTR(MP_QSTR_ec_pubkey_create), MP_ROM_PTR(&usecp256k1_ec_pubkey_create_obj) },
    { MP_ROM_QSTR(MP_QSTR_ec_pubkey_parse), MP_ROM_PTR(&usecp256k1_ec_pubkey_parse_obj) },
    { MP_ROM_QSTR(MP_QSTR_ec_pubkey_serialize), MP_ROM_PTR(&usecp256k1_ec_pubkey_serialize_obj) },
    { MP_ROM_QSTR(MP_QSTR_ecdsa_signature_parse_compact), MP_ROM_PTR(&usecp256k1_ecdsa_signature_parse_compact_obj) },
    { MP_ROM_QSTR(MP_QSTR_ecdsa_signature_parse_der), MP_ROM_PTR(&usecp256k1_ecdsa_signature_parse_der_obj) },
    { MP_ROM_QSTR(MP_QSTR_ecdsa_signature_serialize_der), MP_ROM_PTR(&usecp256k1_ecdsa_signature_serialize_der_obj) },
    { MP_ROM_QSTR(MP_QSTR_ecdsa_signature_serialize_compact), MP_ROM_PTR(&usecp256k1_ecdsa_signature_serialize_compact_obj) },
    { MP_ROM_QSTR(MP_QSTR_ecdsa_signature_normalize), MP_ROM_PTR(&usecp256k1_ecdsa_signature_normalize_obj) },
    { MP_ROM_QSTR(MP_QSTR_ecdsa_verify), MP_ROM_PTR(&usecp256k1_ecdsa_verify_obj) },
    { MP_ROM_QSTR(MP_QSTR_ecdsa_sign), MP_ROM_PTR(&usecp256k1_ecdsa_sign_obj) },
    { MP_ROM_QSTR(MP_QSTR_ec_seckey_verify), MP_ROM_PTR(&usecp256k1_ec_seckey_verify_obj) },
    { MP_ROM_QSTR(MP_QSTR_ec_privkey_negate), MP_ROM_PTR(&usecp256k1_ec_privkey_negate_obj) },
    { MP_ROM_QSTR(MP_QSTR_ec_pubkey_negate), MP_ROM_PTR(&usecp256k1_ec_pubkey_negate_obj) },
    { MP_ROM_QSTR(MP_QSTR_ec_privkey_tweak_add), MP_ROM_PTR(&usecp256k1_ec_privkey_tweak_add_obj) },
    { MP_ROM_QSTR(MP_QSTR_ec_pubkey_tweak_add), MP_ROM_PTR(&usecp256k1_ec_pubkey_tweak_add_obj) },
    { MP_ROM_QSTR(MP_QSTR_ec_privkey_tweak_mul), MP_ROM_PTR(&usecp256k1_ec_privkey_tweak_mul_obj) },
    { MP_ROM_QSTR(MP_QSTR_ec_pubkey_tweak_mul), MP_ROM_PTR(&usecp256k1_ec_pubkey_tweak_mul_obj) },
    { MP_ROM_QSTR(MP_QSTR_ec_pubkey_combine), MP_ROM_PTR(&usecp256k1_ec_pubkey_combine_obj) },
    { MP_ROM_QSTR(MP_QSTR_EC_COMPRESSED), MP_ROM_INT(SECP256K1_EC_COMPRESSED) },
    { MP_ROM_QSTR(MP_QSTR_EC_UNCOMPRESSED), MP_ROM_INT(SECP256K1_EC_UNCOMPRESSED) },
};
STATIC MP_DEFINE_CONST_DICT(secp256k1_module_globals, secp256k1_module_globals_table);

// Define module object.
const mp_obj_module_t secp256k1_user_cmodule = {
    .base = { &mp_type_module },
    .globals = (mp_obj_dict_t*)&secp256k1_module_globals,
};

// Register the module to make it available in Python
MP_REGISTER_MODULE(MP_QSTR_secp256k1, secp256k1_user_cmodule, MODULE_SECP256K1_ENABLED);
