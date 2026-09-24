(function($){
	"use strict";

	$(window).on('elementor/frontend/init', function () {

		
		/* slide portfolio */
        elementorFrontend.hooks.addAction('frontend/element_ready/ova_por_slide.default', function(){
         $(".ova_por_slide .slide-portfolio").each(function(){
           var owlsl = $(this);
           var owlsl_ops = owlsl.data('options') ? owlsl.data('options') : {};

           var responsive_value = {
               0:{
                 items:1,
                 nav:false
               },
               576:{
                 items:1
               },
               992:{
                 items:2
               },
               1170:{
                 items:owlsl_ops.items
               }
           };
           
           owlsl.owlCarousel({
             margin: owlsl_ops.margin,
             items: owlsl_ops.items,
             loop: owlsl_ops.loop,
             autoplay: owlsl_ops.autoplay,
             autoplayTimeout: owlsl_ops.autoplayTimeout,
             center: false,
             nav: owlsl_ops.nav,
             dots: owlsl_ops.dots,
             thumbs: owlsl_ops.thumbs,
             autoplayHoverPause: owlsl_ops.autoplayHoverPause,
             slideBy: owlsl_ops.slideBy,
             smartSpeed: owlsl_ops.smartSpeed,
             navText:[
             '<i class="fa fa-angle-left" ></i>',
             '<i class="fa fa-angle-right" ></i>'
             ],
             responsive: responsive_value,
           });

            owlsl.find(".owl-nav button.owl-prev").attr("title", "Previous");
            owlsl.find(".owl-nav button.owl-next").attr("title", "Next");
            owlsl.find(".owl-dots button").attr("title", "Dots");

         });
      });
      /* end slide portfolio */		

   });
})(jQuery);
