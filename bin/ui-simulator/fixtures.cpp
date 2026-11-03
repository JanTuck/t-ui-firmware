#include <cstdint>
#include <cstdio>
#include <cstring>
extern "C" int tdeck_nodes_list(uint32_t *out, int maxN) { int n = maxN < 3 ? maxN : 3; for(int i=0;i<n;++i)out[i]=i+1; return n; }
extern "C" const char *tdeck_node_name(uint32_t n) { return n==1 ? "Trail base" : n==2 ? "North ridge" : "Harbour"; }
extern "C" uint32_t tdeck_node_age_secs(uint32_t n) { return n*60; }
extern "C" int tdeck_node_battery(uint32_t n) { return 90-n*10; }
extern "C" bool tdeck_node_position(uint32_t, int32_t *lat, int32_t *lon) { *lat=557000000; *lon=126000000; return true; }
extern "C" bool tdeck_node_is_favorite(uint32_t n) { return n==1; }
extern "C" void tdeck_node_set_favorite(uint32_t, bool) {}
extern "C" bool tdeck_gps_position(int32_t *lat, int32_t *lon) { *lat=556000000; *lon=125000000; return true; }
extern "C" void tui_open_chat_with(uint32_t) {}
extern "C" void tui_show_node_on_map(uint32_t, int32_t, int32_t) {}
extern "C" bool notif_unread_from(uint32_t) { return false; }
extern "C" void tui_trace_route(uint32_t) {}
extern "C" void tui_request_position(uint32_t) {}
extern "C" int tdeck_channel_count() { return 1; }
extern "C" const char *tdeck_channel_name(int) { return "LongFast"; }
extern "C" int tdeck_channel_role(int) { return 1; }
extern "C" int tdeck_channel_precision(int) { return 32; }
extern "C" int tdeck_channel_nodes(int, uint32_t *out, int maxN) { return tdeck_nodes_list(out,maxN); }
extern "C" void tui_open_channel_chat(uint8_t) {}
extern "C" int tui_dm_conversations(uint32_t *out, int maxN) { if(maxN<1)return 0; out[0]=1; return 1; }
extern "C" bool tui_dm_last_text(uint32_t, char *out, int n) { snprintf(out,n,"Meet at the trail head"); return true; }
extern "C" void emoji_to_text(const char *in, char *out, size_t n) { snprintf(out,n,"%s",in); }
uint32_t unread_get(uint32_t) { return 0; }
