#include "stm32469i_discovery_lcd.h"

static void draw_bitmap(const uint8_t * arr, size_t len, size_t w, uint16_t x0, uint16_t y0, uint16_t scale, uint8_t fill, uint16_t stroke){
    for(int i=0; i<len; i++){
        uint16_t x = (i % w) * 8;
        uint16_t y = i/w;
        for(int j=0; j<8; j++){
            if((arr[i] >> (7-j)) & 0x01){
                if(fill){
                    BSP_LCD_FillRect(x0+x*scale+j*scale-stroke, y0+y*scale-stroke, scale+2*stroke, scale+2*stroke);
                }else{
                    BSP_LCD_DrawRect(x0+x*scale+j*scale-stroke, y0+y*scale-stroke, scale+2*stroke, scale+2*stroke);
                }
            }
        }
    }
}

void draw_logo(uint16_t x0, uint16_t y0, uint16_t scale){
    static const uint8_t specter_r[] = {
        0b00000111, 0b10000000,
        0b00011111, 0b11100000,
        0b00111111, 0b11110000,
        0b01111111, 0b11111000,
        0b01111111, 0b11111000,
        0b01111111, 0b11111000,
        0b11111111, 0b11111100,
        0b11111111, 0b11111100,
        0b11111111, 0b11111100,
        0b11111111, 0b11111100,
        0b11111111, 0b11111100,
        0b11011100, 0b11101100,
        0b10001100, 0b11000100,
    };
    static const uint8_t specter_w[] = {
        0, 0,
        0, 0,
        0, 0,
        0b00001100, 0b00110000,
        0b00011110, 0b01111000,
        0b00011110, 0b01111000,
        0b00011110, 0b01111000,
        0b00001100, 0b00110000,
    };
    static const uint8_t specter_b[] = {
        0, 0,
        0, 0,
        0, 0,
        0, 0,
        0b00000110, 0b00011000,
        0b00000110, 0b00011000,
    };
    BSP_LCD_SetTextColor(0xFF000000);
    draw_bitmap(specter_r, sizeof(specter_r), 2, x0, y0, scale, 1, (scale+1)/2);
    BSP_LCD_SetTextColor(0xFFD0021B);
    draw_bitmap(specter_r, sizeof(specter_r), 2, x0, y0, scale, 1, 0);
    BSP_LCD_SetTextColor(0xFF9C182D);
    draw_bitmap(specter_r, sizeof(specter_r), 2, x0, y0, scale, 0, 0);
    BSP_LCD_SetTextColor(0xFFFFFFFF);
    draw_bitmap(specter_w, sizeof(specter_w), 2, x0, y0, scale, 1, 0);
    BSP_LCD_SetTextColor(0xFFC2C2C2);
    draw_bitmap(specter_w, sizeof(specter_w), 2, x0, y0, scale, 0, 0);
    BSP_LCD_SetTextColor(0xFF4A90E2);
    draw_bitmap(specter_b, sizeof(specter_b), 2, x0, y0, scale, 1, 0);
    BSP_LCD_SetTextColor(0xFF356FB2);
    draw_bitmap(specter_b, sizeof(specter_b), 2, x0, y0, scale, 0, 0);
}
