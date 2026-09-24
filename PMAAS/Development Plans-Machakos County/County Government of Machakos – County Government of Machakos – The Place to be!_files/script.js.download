(function($){
	"use strict";
	$(document).ready(function(){

		/* Scroll to top */
		egovt_scrollUp();
		function egovt_scrollUp(options) {
		           
		    var defaults = {
		        scrollName: 'scrollUp', 
		        topDistance: 600, 
		        topSpeed: 800, 
		        animation: 'fade', 
		        animationInSpeed: 200, 
		        animationOutSpeed: 200, 
		        scrollText: '<i class="fas fa-angle-up"></i>', 
		        scrollImg: false, 
		        activeOverlay: false 
		    };

		    var o = $.extend({}, defaults, options),
		            scrollId = '#' + o.scrollName;


		    $('<a/>', {
		        id: o.scrollName,
		        href: '#top',
		        title: ScrollUpText.value
		    }).appendTo('body');


		    if (!o.scrollImg) {

		        $(scrollId).html(o.scrollText);
		    }


		    $(scrollId).css({'display': 'none', 'position': 'fixed', 'z-index': '2147483647'});


		    if (o.activeOverlay) {
		        $("body").append("<div id='" + o.scrollName + "-active'></div>");
		        $(scrollId + "-active").css({'position': 'absolute', 'top': o.topDistance + 'px', 'width': '100%', 'border-top': '1px dotted ' + o.activeOverlay, 'z-index': '2147483647'});
		    }


		    $(window).scroll(function () {
		        switch (o.animation) {
		            case "fade":
		                $(($(window).scrollTop() > o.topDistance) ? $(scrollId).fadeIn(o.animationInSpeed) : $(scrollId).fadeOut(o.animationOutSpeed));
		                break;
		            case "slide":
		                $(($(window).scrollTop() > o.topDistance) ? $(scrollId).slideDown(o.animationInSpeed) : $(scrollId).slideUp(o.animationOutSpeed));
		                break;
		            default:
		                $(($(window).scrollTop() > o.topDistance) ? $(scrollId).show(0) : $(scrollId).hide(0));
		        }
		    });

		    
		    $(scrollId).on( "click", function (event) {
		        $('html, body').animate({scrollTop: 0}, o.topSpeed);
		        event.preventDefault();
		    });

		}

		/* Fix empty menu in test_uni_data */
		if( $( '.widget_nav_menu ul li' ).length > 0 ){
			$( '.widget_nav_menu ul li a:empty' ).parent().css('display','none');
		}

		/* Select 2 */
		$('select[name="ovaev_type"]').select2({ 
			width: '100%'
		});
		
		/* Popup Image - PrettyPhoto */
		if( $("a[data-gal^='prettyPhoto']").length > 0 ){
		 	$("a[data-gal^='prettyPhoto']").prettyPhoto({hook: 'data-gal', theme: 'facebook',slideshow:5000, autoplay_slideshow:true});
	    }
	    

	    $( '.ovatheme_header_default li.menu-item button.dropdown-toggle').off('click').on( 'click', function() {
		    $(this).parent().toggleClass('active_sub');
		});


	    // feather icon
	    feather.replace({ role: 'img', 'aria-label': "Icon" });

	    //add padding widget li list product
	   
	    $( ".woocommerce .ova-shop-wrap .woo-sidebar .widget_products ul.product_list_widget li" ).each(function( index ) {
	    	var that = $(this);
			if( that.find('.woocommerce-Price-amount').length == 0 ){
				that.css('padding-bottom', '67px');
			}
			var title = that.find('.product-title').text();
			var result = title.substr(0, 22);

			that.find('.product-title').text(result);

		});

		if($('#woo-sidebar').length <=0 ){
			$('.ova-shop-wrap .content-area').css({'flex':'0 0 100%', 'padding-left':'0px'});
		}

		/* Popup Image - PrettyPhoto */
		if($().prettyPhoto) {
			if( $("a[data-gal^='prettyPhoto']").length > 0 ){
			 	$("a[data-gal^='prettyPhoto']").prettyPhoto({hook: 'data-gal', theme: 'facebook',slideshow:5000, autoplay_slideshow:true});
		    }
		}

		$('.egovt-login-register-woo li a').on('click', function(){
			var type = $(this).data('type');
			$('.egovt-login-register-woo li').removeClass('active');
			$(this).parent('li').addClass('active');
			if( type === 'login' ){


				$('.woocommerce #customer_login .woocommerce-form.woocommerce-form-login').css('display', 'block');
				$('.woocommerce #customer_login .woocommerce-form.woocommerce-form-register').css('display', 'none');
			} else if( type === 'register' ){
				$('.woocommerce #customer_login .woocommerce-form.woocommerce-form-register').css('display', 'block');
				$('.woocommerce #customer_login .woocommerce-form.woocommerce-form-login').css('display', 'none');
			}
		})

		if( $('.col_equal .ovaev-event-element.version_1').length > 0 ){
			var width_screen = window.screen.availWidth;
			if( width_screen > 767 ){
				var height_event_element = $('.ovaev-event-element.version_1').innerHeight();

				if( $('.col_equal .blog-grid article.post-wrap .wrap-article').length > 0 ){
					$('.col_equal .blog-grid article.post-wrap .wrap-article').css('height', height_event_element + 'px' )
				}
			}			
		}
		$('.dropdown-toggle').on('click', function(){
			$(this).parent('li').parent('.dropdown-menu').css({'opacity':1,'visibility': 'visible', 'top': '100%', 'display': 'block', 'box-shadow': 'none'});
		});

		 $('.ova_single_give_form .give_form_info').tabs();


		if($('.egovt_stretch_column_left').length != null ){
			egovt_calculate_width( '.egovt_stretch_column_left' );
		}
		if($('.egovt_stretch_column_right').length != null ){
			egovt_calculate_width( '.egovt_stretch_column_right' );
		}
		

	});	


	/* Archive Give Video */
	if( $(".archive_give_donation .media .video").length > 0 ){
	 $(".archive_give_donation .media .video").fancybox({
	    iframe : {
	       css : {
	          maxWidth : '80%',
	       }
	    }
	 });
	}
  
  

	

	// Calculate width with special class
	function egovt_calculate_width( directly ){

		if( $(directly).length ){

			var width_win = $(window).outerWidth();

			if( directly == '.egovt_stretch_column_left' ){

				var col_offset = $(directly).offset();
				var myLeftLineWidth = col_offset.left;
				var width_left = $(directly).outerWidth() + myLeftLineWidth ;	
				
				

				$('.egovt_stretch_column_left .elementor-column-wrap').css('width', width_left);
				$('.egovt_stretch_column_left .elementor-column-wrap').css('margin-left', -myLeftLineWidth);
			}

			if( directly == '.egovt_stretch_column_right' ){

				var $whatever        = $('.egovt_stretch_column_right');
				var ending_right     = ($(window).width() - ($whatever.offset().left + $whatever.outerWidth()));
				
				var myrightLineWidth = window.innerWidth - ending_right;
				var width_right = $(directly).outerWidth() + myrightLineWidth;


				$('.egovt_stretch_column_right .elementor-column-wrap').css('width', width_right);
				$('.egovt_stretch_column_right .elementor-column-wrap').css('margin-right', -ending_right);
			}
		}

	}


	$(window).resize(function () {
		if($('.egovt_stretch_column_left').length != null ){
	    	egovt_calculate_width('.egovt_stretch_column_left');
		}
		if($('.egovt_stretch_column_right').length != null ){
	    	egovt_calculate_width('.egovt_stretch_column_right');
		}
	});

	
	

})(jQuery);