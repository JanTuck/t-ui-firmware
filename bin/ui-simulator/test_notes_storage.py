"""Run the production Notes save routine against SD failure injection."""
from pathlib import Path
import subprocess,tempfile
root=Path(__file__).resolve().parents[2]
s=(root/'lib/meshtastic-device-ui/source/graphics/TFT/NotesApp.cpp').read_text()
a=s.index('bool saveCurrentNote(');b=s.index('\n#else',a)
fits=s[s.index('bool noteFits('):s.index('const char *saveError(')]
recover=s[s.index('bool recoverNoteSave('):s.index('// scan /notes')]
loader=s[s.index('char *readNote('):s.index('bool saveCurrentNote(')]
source=r'''
#include <cassert>
#include <cstring>
#include <cstdio>
#include <string>
#include <map>
#include <cstdint>
#include <cstdlib>
constexpr size_t kMaxNoteBytes=4000;
constexpr int O_RDONLY=0,O_WRONLY=1,O_CREAT=2,O_EXCL=4;
struct State { std::map<std::string,std::string> files; bool openFail=false,writeFail=false,syncFail=false,closeFail=false,removeFail=false; int renameFail=0,calls=0; } disk;
struct FsFile {
 std::string path; bool good=false;
 explicit operator bool() const {return good;}
 size_t size(){return disk.files[path].size();}
 int read(char *p,size_t n){size_t count=std::min(n,size());memcpy(p,disk.files[path].data(),count);return count;}
 size_t write(const uint8_t *p,size_t n){size_t written=disk.writeFail && n ? n-1:n;disk.files[path].append((const char*)p,written);return written;}
 bool sync(){return !disk.syncFail;} bool close(){return !disk.closeFail;}
};
struct SD {
 bool exists(const char *p){return disk.files.count(p);}
 bool mkdir(const char *p){disk.files[p]="";return true;}
 FsFile open(const char *p,int mode){if(disk.openFail || (mode==O_RDONLY && !exists(p)))return {};if(mode!=O_RDONLY)disk.files[p]="";return {p,true};}
 bool remove(const char *p){if(disk.removeFail)return false;disk.files.erase(p);return true;}
 bool rename(const char *a,const char *b){if(++disk.calls==disk.renameFail)return false;if(!exists(a)||exists(b))return false;disk.files[b]=disk.files[a];disk.files.erase(a);return true;}
} SDFs;
const char *editArea="body", *titleArea="Title";
const char *lv_textarea_get_text(const char *p){return p;}
std::string loadedTitle, loadedBody;
void lv_textarea_set_text(const char *p,const char *value){(p==titleArea?loadedTitle:loadedBody)=value;}
constexpr int MALLOC_CAP_SPIRAM=1;
void *heap_caps_malloc(size_t n,int){return malloc(n);}
void heap_caps_free(void *p){free(p);}
bool curReadOnly=false,curIsNew=false,curFromFiles=false;
char curPath[96]="/notes/n001.txt";
'''+fits+recover+loader+s[a:b]+r'''
int main(){
 for(int fail=0;fail<7;++fail){
  disk={};disk.files[curPath]="old";
  disk.openFail=fail==1;disk.writeFail=fail==2;disk.syncFail=fail==3;disk.closeFail=fail==4;
  disk.renameFail=fail==5?1:fail==6?2:0;
  bool ok=saveCurrentNote();assert(ok==(fail==0));assert(disk.files[curPath]==(ok?"Title\nbody":"old"));
  assert(!disk.files.count(std::string(curPath)+".tui-tmp"));
 }
 disk={};curIsNew=true;editArea="";titleArea="";assert(saveCurrentNote());assert(disk.files.empty());assert(saveCurrentNote(true));assert(disk.files[curPath]=="\n");
 disk={};curIsNew=false;curFromFiles=true;editArea="plain file";assert(saveCurrentNote());assert(disk.files[curPath]=="plain file");
 disk={};disk.files[curPath]="old";disk.files[std::string(curPath)+".tui-bak"]="recoverable";assert(!saveCurrentNote());assert(disk.files[curPath]=="old");
 curFromFiles=false;editArea="body";titleArea="Title";
 for(int crash=0;crash<3;++crash){
  disk={};
  if(crash!=0)disk.files[curPath]="committed";
  if(crash!=2)disk.files[std::string(curPath)+".tui-bak"]="original";
  disk.files[std::string(curPath)+".tui-tmp"]="partial";
  assert(recoverNoteSave(curPath));assert(disk.files[curPath]==(crash==0?"original":"committed"));
  assert(!disk.files.count(std::string(curPath)+".tui-tmp"));assert(!disk.files.count(std::string(curPath)+".tui-bak"));
  assert(saveCurrentNote());assert(disk.files[curPath]=="Title\nbody");
 }
 disk={};disk.files[curPath]="old";std::string large(4000,'x');editArea=large.c_str();assert(!saveCurrentNote());assert(disk.files[curPath]=="old");
 curFromFiles=true;assert(saveCurrentNote());assert(disk.files[curPath]==large);
 large += "?";editArea=large.c_str();assert(!saveCurrentNote());assert(disk.files[curPath].size()==4000);
 curFromFiles=false;titleArea="title field";editArea="body field";
 disk={};disk.files[curPath]=std::string(100,'t');loadCurPathIntoEditor();assert(curReadOnly);assert(loadedTitle.empty());assert(loadedBody==std::string(100,'t'));
 disk.files[curPath]="Title\nbody";loadCurPathIntoEditor();assert(!curReadOnly);assert(loadedTitle=="Title" && loadedBody=="body");
 disk.files[curPath]=std::string(4001,'x');loadCurPathIntoEditor();assert(curReadOnly);assert(loadedBody.size()==4000);
 disk.files[curPath]=std::string("hi\0tail",7);loadCurPathIntoEditor();assert(curReadOnly);
 std::string utfTitle;for(int i=0;i<40;i++)utfTitle += "?";disk.files[curPath]=utfTitle+"\nbody";loadCurPathIntoEditor();assert(!curReadOnly);assert(loadedTitle==utfTitle);
 disk.openFail=true;loadCurPathIntoEditor();assert(curReadOnly);assert(loadedBody.empty());
 disk={};disk.files[curPath]="new";disk.files[std::string(curPath)+".tui-bak"]="old";assert(deleteCurrentNote());assert(!disk.files.count(curPath));assert(!disk.files.count(std::string(curPath)+".tui-bak"));
 disk={};disk.files[curPath]="new";disk.files[std::string(curPath)+".tui-bak"]="old";disk.removeFail=true;assert(!deleteCurrentNote());assert(disk.files[curPath]=="new");
 puts("PASS: Notes saves, empty notes, exact Files content, open/write/sync/close/rename failures preserve original");
}
'''
with tempfile.TemporaryDirectory() as directory:
 path=Path(directory);(path/'test.cpp').write_text(source)
 subprocess.run(['g++','-std=c++17','-Wall','-Wextra','-Werror',str(path/'test.cpp'),'-o',str(path/'test')],check=True)
 subprocess.run([str(path/'test')],check=True)
