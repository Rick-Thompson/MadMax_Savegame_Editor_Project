// Brute-force preimages for Avalanche lookup3 hashes over a snake_case wordlist.
// Ported from names.py jenkins(); verified against canonical lookup3 test vectors.
//   ./crack <k> <start> <count>   process items [start,start+count) of the
//   k-token join space (tokens joined with '_'), on the single visible HIP device.
#include <hip/hip_runtime.h>
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <vector>
#include <string>
#include <algorithm>
#include <cstdint>

#define WLEN 20        // max stored bytes per word
#define MAXHITS 8192
#define CK(x) do{ hipError_t e=(x); if(e){fprintf(stderr,"HIP err %s @%d: %s\n",#x,__LINE__,hipGetErrorString(e)); exit(1);} }while(0)

__device__ __forceinline__ uint32_t rotl(uint32_t x,int k){ return (x<<k)|(x>>(32-k)); }
__device__ __forceinline__ void mix(uint32_t&a,uint32_t&b,uint32_t&c){
  a-=c; a^=rotl(c,4);  c+=b;  b-=a; b^=rotl(a,6);  a+=c;
  c-=b; c^=rotl(b,8);  b+=a;  a-=c; a^=rotl(c,16); c+=b;
  b-=a; b^=rotl(a,19); a+=c;  c-=b; c^=rotl(b,4);  b+=a;
}
__device__ __forceinline__ void final3(uint32_t&a,uint32_t&b,uint32_t&c){
  c^=b; c-=rotl(b,14); a^=c; a-=rotl(c,11); b^=a; b-=rotl(a,25);
  c^=b; c-=rotl(b,16); a^=c; a-=rotl(c,4);  b^=a; b-=rotl(a,14); c^=b; c-=rotl(b,24);
}
__device__ uint32_t lookup3(const unsigned char*s,int n){
  uint32_t a,b,c; a=b=c=0xDEADBEEFu + (uint32_t)n;
  int p=0, rem=n;
  while(rem>12){
    a += s[p]|(s[p+1]<<8)|(s[p+2]<<16)|(s[p+3]<<24);
    b += s[p+4]|(s[p+5]<<8)|(s[p+6]<<16)|(s[p+7]<<24);
    c += s[p+8]|(s[p+9]<<8)|(s[p+10]<<16)|(s[p+11]<<24);
    mix(a,b,c); p+=12; rem-=12;
  }
  if(rem==0) return c;                 // only n==0
  uint32_t t0=0,t1=0,t2=0;
  for(int i=0;i<rem;i++){ uint32_t v=s[p+i];
    if(i<4) t0|=v<<(8*i); else if(i<8) t1|=v<<(8*(i-4)); else t2|=v<<(8*(i-8)); }
  a+=t0; b+=t1; c+=t2; final3(a,b,c); return c;
}
__device__ __forceinline__ bool inset(const uint32_t*t,int nt,uint32_t h){
  int lo=0,hi=nt-1;
  while(lo<=hi){ int m=(lo+hi)>>1; uint32_t v=t[m];
    if(v==h) return true; if(v<h) lo=m+1; else hi=m-1; }
  return false;
}
__global__ void crackk(int k,uint32_t V,uint64_t start,uint64_t count,
                       const unsigned char*words,const unsigned char*wl,
                       const uint32_t*targ,int nt,
                       uint64_t*hitgid,uint32_t*hithash,unsigned*hitcnt){
  uint64_t tid=(uint64_t)blockIdx.x*blockDim.x+threadIdx.x;
  if(tid>=count) return;
  uint64_t gid=start+tid, g=gid;
  unsigned char buf[64]; int len=0;
  for(int t=0;t<k;t++){
    uint32_t wi=g%V; g/=V;
    int L=wl[wi]; const unsigned char*w=words+(uint64_t)wi*WLEN;
    if(t){ buf[len++]='_'; }
    for(int i=0;i<L;i++) buf[len++]=w[i];
  }
  uint32_t h=lookup3(buf,len);
  if(inset(targ,nt,h)){
    unsigned idx=atomicAdd(hitcnt,1u);
    if(idx<MAXHITS){ hitgid[idx]=gid; hithash[idx]=h; }
  }
}
int main(int argc,char**argv){
  if(argc<4){ fprintf(stderr,"usage: crack k start count\n"); return 2; }
  int k=atoi(argv[1]); uint64_t start=strtoull(argv[2],0,10), count=strtoull(argv[3],0,10);
  // load vocab
  std::vector<std::string> W; { FILE*f=fopen("vocab.txt","r"); if(!f){perror("vocab");return 1;}
    char line[256]; while(fgets(line,sizeof line,f)){ int n=strlen(line); while(n&&(line[n-1]=='\n'||line[n-1]=='\r'))line[--n]=0;
      if(n>0&&n<=WLEN) W.push_back(line); } fclose(f); }
  uint32_t V=W.size();
  std::vector<unsigned char> words(V*WLEN,0), wl(V);
  for(uint32_t i=0;i<V;i++){ memcpy(&words[(size_t)i*WLEN],W[i].data(),W[i].size()); wl[i]=W[i].size(); }
  // load + sort targets
  std::vector<uint32_t> T; { FILE*f=fopen("targets.txt","r"); if(!f){perror("targets");return 1;}
    char line[64]; while(fgets(line,sizeof line,f)){ uint32_t h; if(sscanf(line,"%x",&h)==1) T.push_back(h);} fclose(f); }
  std::sort(T.begin(),T.end()); int nt=T.size();
  unsigned char*dW,*dwl; uint32_t*dT; uint64_t*dhg; uint32_t*dhh; unsigned*dhc;
  CK(hipMalloc(&dW,words.size())); CK(hipMalloc(&dwl,V)); CK(hipMalloc(&dT,nt*4));
  CK(hipMalloc(&dhg,MAXHITS*8)); CK(hipMalloc(&dhh,MAXHITS*4)); CK(hipMalloc(&dhc,4));
  CK(hipMemcpy(dW,words.data(),words.size(),hipMemcpyHostToDevice));
  CK(hipMemcpy(dwl,wl.data(),V,hipMemcpyHostToDevice));
  CK(hipMemcpy(dT,T.data(),nt*4,hipMemcpyHostToDevice));
  CK(hipMemset(dhc,0,4));
  int TPB=256; uint64_t blocks=(count+TPB-1)/TPB;
  // cap blocks per launch to keep kernels short; tile if needed
  uint64_t done=0; const uint64_t CHUNK=(uint64_t)200000*TPB; // ~51M items/launch
  while(done<count){ uint64_t c=std::min(CHUNK,count-done); uint64_t bl=(c+TPB-1)/TPB;
    hipLaunchKernelGGL(crackk,dim3(bl),dim3(TPB),0,0,k,V,start+done,c,dW,dwl,dT,nt,dhg,dhh,dhc);
    CK(hipGetLastError()); CK(hipDeviceSynchronize()); done+=c; }
  unsigned hc; CK(hipMemcpy(&hc,dhc,4,hipMemcpyDeviceToHost));
  unsigned n=hc<MAXHITS?hc:MAXHITS;
  std::vector<uint64_t> hg(n); std::vector<uint32_t> hh(n);
  if(n){ CK(hipMemcpy(hg.data(),dhg,n*8,hipMemcpyDeviceToHost)); CK(hipMemcpy(hh.data(),dhh,n*4,hipMemcpyDeviceToHost)); }
  for(unsigned i=0;i<n;i++){ uint64_t g=hg[i]; std::string s;
    for(int t=0;t<k;t++){ uint32_t wi=g%V; g/=V; if(t)s+="_"; s+=W[wi]; }
    // rebuild in emit order (tokens were appended t=0 first)
    std::string out; { uint64_t gg=hg[i]; std::vector<std::string> toks;
      for(int t=0;t<k;t++){ uint32_t wi=gg%V; gg/=V; toks.push_back(W[wi]); }
      for(int t=0;t<k;t++){ if(t)out+="_"; out+=toks[t]; } }
    printf("HIT %08X %s\n",hh[i],out.c_str()); }
  fprintf(stderr,"k=%d range[%llu,%llu) V=%u targets=%d hits=%u\n",k,(unsigned long long)start,(unsigned long long)(start+count),V,nt,hc);
  return 0;
}
