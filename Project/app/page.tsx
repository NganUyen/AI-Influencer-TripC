"use client";

import Link from "next/link";

export default function HomePage() {
  return (
    <div className="bg-[#f8f7f0] font-[Lexend] text-[#2e2f2c] min-h-screen flex flex-col items-center overflow-x-hidden selection:bg-[#a03929]/10 selection:text-[#a03929]">
      <style jsx global>{`
        @import url('https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@400;500;600;700;800&family=Lexend:wght@300;400;500;600&display=swap');
        
        h1, h2, h3 { font-family: 'Plus Jakarta Sans', sans-serif; }
        .material-symbols-outlined {
          font-variation-settings: 'FILL' 0, 'wght' 400, 'GRAD' 0, 'opsz' 24;
        }
        .gradient-text {
          background: linear-gradient(to right, #a03929, #fd7d68);
          -webkit-background-clip: text;
          -webkit-text-fill-color: transparent;
        }
        .brand-shadow {
          box-shadow: 0 20px 40px rgba(0, 0, 0, 0.1), 0 10px 15px rgba(0, 0, 0, 0.05);
        }
      `}</style>

      {/* Decorative Background Elements */}
      <div className="fixed inset-0 pointer-events-none z-0">
        <div className="absolute -top-24 -left-24 w-96 h-96 bg-[#a03929]/5 rounded-full blur-[100px]"></div>
        <div className="absolute bottom-0 right-0 w-[600px] h-[600px] bg-[#fd7d68]/5 rounded-full blur-[150px]"></div>
      </div>

      

      <main className="w-full max-w-7xl px-8 pt-20 pb-32 z-10">
        {/* Hero Section */}
        <section className="flex flex-col lg:flex-row items-center gap-20">
          <div className="w-full lg:w-3/5 space-y-10 text-center lg:text-left">
            <div className="inline-flex items-center gap-2 px-4 py-2 bg-white rounded-full text-[#a03929] font-bold text-sm tracking-wide border border-[#a03929]/10 shadow-sm">
              <span className="material-symbols-outlined text-base">verified</span>
              <span>HỆ SINH THÁI AI INFLUENCER SỐ 1</span>
            </div>
            <h1 className="text-6xl md:text-8xl font-extrabold tracking-tight leading-[1.05] text-[#2e2f2c]">
              Vận hành <span className="gradient-text">Influencer</span><br/> 
              tự động hóa 100%.
            </h1>
            <p className="text-xl md:text-2xl text-[#2e2f2c]/60 max-w-2xl leading-relaxed font-medium">
              Xây dựng, quản lý và tối ưu hóa tài khoản mạng xã hội của bạn thông qua sức mạnh AI Engine tiên tiến nhất thế giới.
            </p>
            <div className="flex flex-wrap justify-center lg:justify-start gap-6 pt-4">
              <Link href="/auth" className="px-10 py-5 bg-[#a03929] text-white rounded-full font-bold text-lg brand-shadow transition-all hover:scale-105 active:scale-95 flex items-center gap-3">
                 Tạo tài khoản miễn phí
                 <span className="material-symbols-outlined">arrow_forward</span>
              </Link>
              <button className="px-10 py-5 bg-white text-[#2e2f2c] rounded-full font-bold text-lg border border-[#2e2f2c]/10 transition-all hover:bg-[#f8f7f0]">
                Xem bản Demo
              </button>
            </div>
          </div>
          
          <div className="w-full lg:w-2/5">
             <div className="relative aspect-[4/5] bg-white rounded-3xl brand-shadow border border-[#2e2f2c]/5 overflow-hidden group">
                <img 
                  src="https://images.unsplash.com/photo-1618005182384-a83a8bd57fbe?auto=format&fit=crop&q=80&w=1000" 
                  alt="AI-Influencer AI Visualization"
                  className="w-full h-full object-cover opacity-90 transition-transform duration-1000 group-hover:scale-110"
                />
                <div className="absolute inset-0 bg-gradient-to-t from-[#f8f7f0] via-transparent to-transparent"></div>
                
                {/* Floating Stats UI */}
                <div className="absolute bottom-10 left-10 right-10 p-8 bg-white/80 backdrop-blur-xl rounded-3xl border border-white/40 shadow-2xl space-y-4 translate-y-4 group-hover:translate-y-0 transition-transform duration-500">
                   <div className="flex justify-between items-center">
                     <span className="text-[10px] font-black uppercase tracking-widest text-[#a03929]">Tình trạng vận hành</span>
                     <div className="flex gap-1">
                        <div className="w-1.5 h-1.5 rounded-full bg-[#a03929] animate-pulse"></div>
                        <div className="w-1.5 h-1.5 rounded-full bg-[#a03929] animate-pulse delay-75"></div>
                        <div className="w-1.5 h-1.5 rounded-full bg-[#a03929] animate-pulse delay-150"></div>
                     </div>
                   </div>
                   <div className="h-2 w-full bg-[#2e2f2c]/5 rounded-full overflow-hidden">
                      <div className="h-full w-[85%] bg-[#a03929] rounded-full"></div>
                   </div>
                   <p className="text-[#2e2f2c] text-sm font-bold">85% Persona Voice Accuracy</p>
                </div>
             </div>
          </div>
        </section>

        {/* Feature Bento Grid */}
        <section className="mt-40 grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-8">
          <FeatureCard 
            icon="hub" 
            title="Đồng bộ đa nền tảng" 
            description="Kết nối TikTok, Instagram, Youtube chỉ trong một nốt nhạc qua hệ thống OAuth bảo mật." 
          />
          <FeatureCard 
            icon="psychology" 
            title="Linh hồn AI" 
            description="Mỗi Influencer sở hữu một cá tính riêng, có khả năng học hỏi và tương tác như người thật." 
          />
          <FeatureCard 
            icon="auto_videocam" 
            title="Sản xuất hàng loạt" 
            description="Tự động hóa toàn bộ quy trình từ lên ý tưởng, viết kịch bản đến dựng video clip." 
          />
          <FeatureCard 
            icon="query_stats" 
            title="Tối ưu dữ liệu" 
            description="Phân tích hiệu suất bài đăng theo thời gian thực để tinh chỉnh chiến lược nội dung." 
          />
          <FeatureCard 
            icon="forum" 
            title="Tương tác thông minh" 
            description="Tự động trả lời bình luận và tin nhắn với phong cách đặc trưng của từng persona." 
          />
          <FeatureCard 
            icon="verified_user" 
            title="Kiểm soát tuyệt đối" 
            description="Mọi nội dung đều được phê duyệt bởi bạn trước khi xuất bản ra thế giới bên ngoài." 
          />
        </section>
      </main>

      <footer className="w-full bg-[#2e2f2c] text-[#f8f7f0] py-24 px-8 z-10 overflow-hidden">
        <div className="max-w-7xl mx-auto flex flex-col md:flex-row justify-between items-start gap-20">
          <div className="max-w-md space-y-8">
            <div className="flex items-center gap-3">
              <div className="w-10 h-10 bg-white rounded-xl flex items-center justify-center">
                <span className="material-symbols-outlined text-[#2e2f2c] text-2xl">auto_awesome</span>
              </div>
              <span className="text-2xl font-bold tracking-tighter">AI-Influencer</span>
            </div>
            <p className="text-lg text-[#f8f7f0]/60 leading-relaxed font-medium">
              Cách thức thương hiệu của bạn giao tiếp với thế giới đang thay đổi. Định hình tương lai cùng AI-Influencer.
            </p>
          </div>
          <div className="grid grid-cols-2 md:grid-cols-3 gap-16">
            <div className="space-y-6">
              <h4 className="text-[10px] font-black uppercase tracking-widest text-[#f8f7f0]/40">Sản phẩm</h4>
              <ul className="space-y-4 text-sm font-bold">
                <li><a className="hover:text-[#a03929] transition-colors" href="#">AI Engine</a></li>
                <li><a className="hover:text-[#a03929] transition-colors" href="#">Studio Hub</a></li>
                <li><a className="hover:text-[#a03929] transition-colors" href="#">Persona Registry</a></li>
              </ul>
            </div>
            <div className="space-y-6">
              <h4 className="text-[10px] font-black uppercase tracking-widest text-[#f8f7f0]/40">Công ty</h4>
              <ul className="space-y-4 text-sm font-bold">
                <li><a className="hover:text-[#a03929] transition-colors" href="#">Giới thiệu</a></li>
                <li><a className="hover:text-[#a03929] transition-colors" href="#">Nghề nghiệp</a></li>
                <li><a className="hover:text-[#a03929] transition-colors" href="#">Liên hệ</a></li>
              </ul>
            </div>
            <div className="space-y-6">
              <h4 className="text-[10px] font-black uppercase tracking-widest text-[#f8f7f0]/40">Hệ thống</h4>
              <ul className="space-y-4 text-sm font-bold">
                <li><a className="hover:text-[#a03929] transition-colors" href="/ops">Operator Dashboard</a></li>
                <li><a className="hover:text-[#a03929] transition-colors" href="/auth">Customer Portal</a></li>
              </ul>
            </div>
          </div>
        </div>
        <div className="max-w-7xl mx-auto mt-24 pt-10 border-t border-white/10 flex flex-col md:flex-row justify-between items-center gap-6">
           <p className="text-[10px] font-black uppercase tracking-widest opacity-40">AI-Influencer Factory 2024. All rights reserved.</p>
           <div className="flex gap-8 text-[10px] font-black uppercase tracking-widest opacity-60">
             <a className="hover:text-white" href="#">Privacy Policy</a>
             <a className="hover:text-white" href="#">Terms of Service</a>
           </div>
        </div>
      </footer>
    </div>
  );
}

function FeatureCard({ icon, title, description }: { icon: string; title: string; description: string }) {
  return (
    <div className="p-10 bg-white rounded-3xl border border-[#2e2f2c]/5 shadow-sm transition-all hover:scale-[1.02] hover:shadow-2xl hover:shadow-[#a03929]/5 group">
      <div className="w-14 h-14 bg-[#f8f7f0] rounded-2xl flex items-center justify-center mb-8 transition-colors group-hover:bg-[#a03929]/10">
        <span className="material-symbols-outlined text-[#a03929] text-3xl">{icon}</span>
      </div>
      <h3 className="text-2xl font-bold mb-4 text-[#2e2f2c] tracking-tight">{title}</h3>
      <p className="text-[#2e2f2c]/60 text-base leading-relaxed font-medium">{description}</p>
    </div>
  );
}
