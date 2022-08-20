/**
 * @file px_img.c
 *
 */

/*********************
 *      INCLUDES
 *********************/
#include "px_img.h"
#if LV_USE_IMG != 0

/*Testing of dependencies*/
#if LV_USE_LABEL == 0
#error "px_img: lv_label is required. Enable it in lv_conf.h (LV_USE_LABEL  1) "
#endif

#include "../lvgl/src/lv_themes/lv_theme.h"
#include "../lvgl/src/lv_draw/lv_img_decoder.h"
#include "../lvgl/src/lv_misc/lv_fs.h"
#include "../lvgl/src/lv_misc/lv_txt.h"
#include "../lvgl/src/lv_misc/lv_log.h"
#include "../lvgl/src/lv_objx/lv_img.h"

/*********************
 *      DEFINES
 *********************/

/**********************
 *      TYPEDEFS
 **********************/

/**********************
 *  STATIC PROTOTYPES
 **********************/
static bool px_img_design(lv_obj_t * img, const lv_area_t * mask, lv_design_mode_t mode);
static lv_res_t px_img_signal(lv_obj_t * img, lv_signal_t sign, void * param);

/**********************
 *  STATIC VARIABLES
 **********************/
static lv_signal_cb_t ancestor_signal;

/**********************
 *      MACROS
 **********************/

/**********************
 *   GLOBAL FUNCTIONS
 **********************/

/**
 * Create an image objects
 * @param par pointer to an object, it will be the parent of the new button
 * @param copy pointer to a image object, if not NULL then the new object will be copied from it
 * @return pointer to the created image
 */
lv_obj_t * px_img_create(lv_obj_t * par, const lv_obj_t * copy)
{
    LV_LOG_TRACE("image create started");

    lv_obj_t * new_img = NULL;

    /*Create a basic object*/
    new_img = lv_obj_create(par, copy);
    lv_mem_assert(new_img);
    if(new_img == NULL) return NULL;

    if(ancestor_signal == NULL) ancestor_signal = lv_obj_get_signal_cb(new_img);

    /*Extend the basic object to image object*/
    lv_img_ext_t * ext = lv_obj_allocate_ext_attr(new_img, sizeof(lv_img_ext_t));
    lv_mem_assert(ext);
    if(ext == NULL) return NULL;

    ext->src       = NULL;
    ext->src_type  = LV_IMG_SRC_UNKNOWN;
    ext->cf        = LV_IMG_CF_UNKNOWN;
    ext->w         = lv_obj_get_width(new_img);
    ext->h         = lv_obj_get_height(new_img);
    ext->auto_size = 1;
    ext->offset.x  = 0;
    ext->offset.y  = 0;

    /*Init the new object*/
    lv_obj_set_signal_cb(new_img, px_img_signal);
    lv_obj_set_design_cb(new_img, px_img_design);

    if(copy == NULL) {
        lv_obj_set_click(new_img, false);
        /* Enable auto size for non screens
         * because image screens are wallpapers
         * and must be screen sized*/
        if(par != NULL) {
            ext->auto_size = 0;
            lv_obj_set_style(new_img, NULL); /*Inherit the style  by default*/
        } else {
            ext->auto_size = 0;
            lv_obj_set_style(new_img, &lv_style_plain); /*Set a style for screens*/
        }
    } else {
        lv_img_ext_t * copy_ext = lv_obj_get_ext_attr(copy);
        ext->auto_size          = copy_ext->auto_size;
        lv_img_set_src(new_img, copy_ext->src);

        /*Refresh the style with new signal function*/
        lv_obj_refresh_style(new_img);
    }

    LV_LOG_INFO("image created");

    return new_img;
}

static bool px_img_design(lv_obj_t * img, const lv_area_t * mask, lv_design_mode_t mode)
{
    const lv_style_t * style = lv_obj_get_style(img);
    lv_img_ext_t * ext       = lv_obj_get_ext_attr(img);
    lv_img_dsc_t * dsc = (lv_img_dsc_t *)ext->src;

    if(mode == LV_DESIGN_COVER_CHK) {
        bool cover = false;
        if(ext->src_type == LV_IMG_SRC_UNKNOWN || ext->src_type == LV_IMG_SRC_SYMBOL) return false;

        if(ext->cf == LV_IMG_CF_TRUE_COLOR || ext->cf == LV_IMG_CF_RAW) cover = lv_area_is_in(mask, &img->coords);

        return cover;
    } else if(mode == LV_DESIGN_DRAW_MAIN) {
        if(ext->h == 0 || ext->w == 0) return true;
        lv_area_t coords;
        lv_opa_t opa_scale = lv_obj_get_opa_scale(img);

        lv_obj_get_coords(img, &coords);

        coords.x1 -= ext->offset.x;
        coords.y1 -= ext->offset.y;

        LV_LOG_TRACE("px_img_design: start to draw image");
        lv_area_t cords_tmp;

        lv_coord_t w = lv_obj_get_width(img);
        // there is always +1 on the right
        lv_coord_t ww = ext->w - 1;
        int scale = w/ww;
        lv_coord_t off = (w - scale*ww)/2;

        cords_tmp.y1 = coords.y1;
        cords_tmp.x1 = coords.x1;

        cords_tmp.y2 = coords.y1 + w;
        cords_tmp.x2 = coords.x1 + w;

        // lv_draw_fill(&cords_tmp, mask, LV_COLOR_MAKE(255,255,255), opa_scale);

        uint16_t idx = 0;
        const uint8_t * data = (uint8_t *)dsc->data;
        lv_color_t c = style->text.color;
        uint16_t border = style->body.border.width;
        if(border > scale){
            border = scale-1; // at least one dark point should remain
        }
        for(lv_coord_t x = 0; x < ww; x++){
            for(lv_coord_t y = 0; y < (ext->h-1); y++){
                cords_tmp.x1 = coords.x1 + off + x*scale;
                cords_tmp.x2 = cords_tmp.x1 + scale - border;
                cords_tmp.y1 = coords.y1 + off + y*scale;
                cords_tmp.y2 = cords_tmp.y1 + scale - border;
                idx = x + y*ext->h;
                uint8_t b = data[idx/8];
                uint8_t s = 7-(idx % 8);
                if((b>>s)&1){
                    lv_draw_fill(&cords_tmp, mask, c, opa_scale);
                }
            }
        }

    }

    return true;
}

/**
 * Signal function of the image
 * @param img pointer to an image object
 * @param sign a signal type from lv_signal_t enum
 * @param param pointer to a signal specific variable
 * @return LV_RES_OK: the object is not deleted in the function; LV_RES_INV: the object is deleted
 */
static lv_res_t px_img_signal(lv_obj_t * img, lv_signal_t sign, void * param)
{
    lv_res_t res;

    /* Include the ancient signal function */
    res = ancestor_signal(img, sign, param);
    if(res != LV_RES_OK) return res;

    lv_img_ext_t * ext = lv_obj_get_ext_attr(img);
    if(sign == LV_SIGNAL_CLEANUP) {
        if(ext->src_type == LV_IMG_SRC_FILE || ext->src_type == LV_IMG_SRC_SYMBOL) {
            lv_mem_free(ext->src);
            ext->src      = NULL;
            ext->src_type = LV_IMG_SRC_UNKNOWN;
        }
    } else if(sign == LV_SIGNAL_STYLE_CHG) {
        /*Refresh the file name to refresh the symbol text size*/
        if(ext->src_type == LV_IMG_SRC_SYMBOL) {
            lv_img_set_src(img, ext->src);
        }
    } else if(sign == LV_SIGNAL_GET_TYPE) {
        lv_obj_type_t * buf = param;
        uint8_t i;
        for(i = 0; i < LV_MAX_ANCESTOR_NUM - 1; i++) { /*Find the last set data*/
            if(buf->type[i] == NULL) break;
        }
        buf->type[i] = "px_img";
    }

    return res;
}

#endif
