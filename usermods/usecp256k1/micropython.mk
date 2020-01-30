BITCOIN_MOD_DIR := $(USERMOD_DIR)

# Add all C files to SRC_USERMOD.
SRC_USERMOD += $(BITCOIN_MOD_DIR)/secp256k1schnorr/src/secp256k1.c
SRC_USERMOD += $(BITCOIN_MOD_DIR)/config/ext_callbacks.c
SRC_USERMOD += $(BITCOIN_MOD_DIR)/libsecp256k1.c

# We can add our module folder to include paths if needed
CFLAGS_USERMOD += -I$(BITCOIN_MOD_DIR)/secp256k1schnorr -I$(BITCOIN_MOD_DIR)/secp256k1schnorr/src -I$(BITCOIN_MOD_DIR)/config -DHAVE_CONFIG_H