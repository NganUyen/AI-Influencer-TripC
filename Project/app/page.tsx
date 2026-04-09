"use client";

import Link from "next/link";
import { Footer } from "@/components/layout/Footer";
import aiAvatarImg from "@/app/dashboard/ai-avatar.jpg";

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
        
        /* Premium card animations */
        @keyframes cardHoverGlow {
          0% { box-shadow: 0 20px 40px rgba(0, 0, 0, 0.1), 0 10px 15px rgba(0, 0, 0, 0.05), 0 0 20px rgba(160, 57, 41, 0); }
          100% { box-shadow: 0 20px 40px rgba(0, 0, 0, 0.1), 0 10px 15px rgba(0, 0, 0, 0.05), 0 0 30px rgba(160, 57, 41, 0.15); }
        }
        
        @keyframes slideUpFade {
          from { opacity: 0; transform: translateY(10px); }
          to { opacity: 1; transform: translateY(0); }
        }
        
        @keyframes badgePulse {
          0%, 100% { transform: scale(1); }
          50% { transform: scale(1.05); }
        }
        
        .card-premium {
          transition: all 0.6s cubic-bezier(0.23, 1, 0.320, 1);
        }
        
        .card-premium:hover {
          animation: cardHoverGlow 0.6s ease-out;
          transform: translateY(-4px);
        }
        
        .content-fade-in {
          animation: slideUpFade 0.7s ease-out forwards;
        }
        
        .badge-hover {
          animation: badgePulse 2.5s ease-in-out infinite;
        }
        
        .badge-hover:hover {
          animation: badgePulse 1s ease-in-out infinite;
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
             <div className="card-premium relative aspect-[4/5] bg-white rounded-3xl brand-shadow border border-[#2e2f2c]/8 overflow-hidden group">
                {/* Background image with overlay */}
                <div className="absolute inset-0">
                  <img 
                    src={aiAvatarImg.src} 
                    alt="AI Video Generation"
                    className="w-full h-full object-cover opacity-20 group-hover:opacity-25 transition-opacity duration-500"
                  />
                  <div className="absolute inset-0 bg-gradient-to-b from-black/5 via-black/8 to-black/12"></div>
                </div>
                
                {/* Content */}
                <div className="relative w-full h-full flex flex-col items-center justify-center px-8 py-10 text-center">
                  {/* Badge */}
                  <div className="badge-hover mb-8 inline-flex items-center gap-2 px-3 py-1 bg-[#a03929]/10 rounded-full border border-[#a03929]/20 transition-all duration-300">
                    <div className="w-2 h-2 rounded-full bg-[#a03929]"></div>
                    <span className="text-xs font-semibold text-[#a03929] uppercase tracking-wide">AI-Powered</span>
                  </div>

                  {/* Main heading */}
                  <h3 className="text-3xl font-extrabold text-[#2e2f2c] mb-3 tracking-tight leading-tight transition-all duration-500 group-hover:text-[#a03929]">
                    Video Content in Seconds
                  </h3>
                  
                  {/* Subheading */}
                  <p className="text-sm text-[#2e2f2c]/70 leading-relaxed mb-10 max-w-sm font-medium">
                    Professional AI-generated videos for creators, influencers, and brands
                  </p>

                  {/* Feature pill */}
                  <div className="mb-8 transition-all duration-500 group-hover:scale-110 group-hover:shadow-lg group-hover:shadow-[#a03929]/20">
                    <div className="inline-block px-4 py-2 bg-white/60 backdrop-blur-sm rounded-full border border-[#a03929]/15">
                      <span className="text-xs text-[#2e2f2c] font-semibold">⚡ Real-Time Output</span>
                    </div>
                  </div>

                  {/* CTA text */}
                  <div className="text-xs text-[#2e2f2c]/60 font-medium">
                    Powered by <span className="font-bold text-[#a03929]">OpenClaw</span>
                  </div>
                </div>

                {/* Bottom accent line */}
                <div className="absolute bottom-0 left-0 right-0 h-1 bg-gradient-to-r from-transparent via-[#a03929] to-transparent opacity-30"></div>
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

      <Footer variant="page" />
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
