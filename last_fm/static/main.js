$(function(){
    /*
    #### ##    ## ########  ######## ##     ## 
     ##  ###   ## ##     ## ##        ##   ##  
     ##  ####  ## ##     ## ##         ## ##   
     ##  ## ## ## ##     ## ######      ###    
     ##  ##  #### ##     ## ##         ## ##   
     ##  ##   ### ##     ## ##        ##   ##  
    #### ##    ## ########  ######## ##     ## 
    */

    $(".release").on("click", ".ignore-artist", function(){
        var artist = $(this).parents(".release").data("artist");
        $.post("/ignore-artist", { "artist" : artist }, function(){
            $(".release:visible").each(function(){
                var $this = $(this);
                if ($this.data("artist") == artist)
                {
                    $this.slideUp();
                }
            });
        });
        return false;
    });

    /*
     ######  ########    ###    ########  ######  
    ##    ##    ##      ## ##      ##    ##    ## 
    ##          ##     ##   ##     ##    ##       
     ######     ##    ##     ##    ##     ######  
          ##    ##    #########    ##          ## 
    ##    ##    ##    ##     ##    ##    ##    ## 
     ######     ##    ##     ##    ##     ######  
    */

    $(".select-all").click(function(){
        var $this = $(this);
        var $div = $this.parents(".checkbox:first");
        while (($div = $div.next()).is(".checkbox"))
        {
            $div.find("input").prop("checked", $this.is(":checked"));
        }
    });

    $(".fixed-header").each(function(){
        var $table = $(this);

        $table.fixedHeaderTable({ footer: true, cloneHeadToFoot: true, fixedColumn: false, height: $(window).height() - $table.offset().top - 15 });
    });

    $(".date-input input").each(function(){
        $(this).datepicker({
            changeYear: true,
            changeMonth: true,
            dateFormat: "dd.mm.yy"
        });
    });

    $("#prediction-table td").on("click", function(){
        flashOtherTable($("#real-table"), $(this));
    });
    $("#real-table td").on("click", function(){
        flashOtherTable($("#prediction-table"), $(this));
    });
    function flashOtherTable($table, $td)
    {
        var $tr = $table.find("tr[rel='" + $td.parent().attr("rel") + "']");
        if ($tr.length)
        {
            $table.parent().scrollTop($table.parent().scrollTop() + $tr.position().top);
            $tr.stop().css("color", "#FF0000").animate({color: "#000000"}, 1500);
        }
    }

    /*        
    ##     ## #### ########    ########     ###    ########     ###    ########  ######## 
    ##     ##  ##     ##       ##     ##   ## ##   ##     ##   ## ##   ##     ## ##       
    ##     ##  ##     ##       ##     ##  ##   ##  ##     ##  ##   ##  ##     ## ##       
    #########  ##     ##       ########  ##     ## ########  ##     ## ##     ## ######   
    ##     ##  ##     ##       ##        ######### ##   ##   ######### ##     ## ##       
    ##     ##  ##     ##       ##        ##     ## ##    ##  ##     ## ##     ## ##       
    ##     ## ####    ##       ##        ##     ## ##     ## ##     ## ########  ######## 
    */

    if (localStorage)
    {
        var $form;

        if (($form = $("form.hit-parade")).length)
        {
            // Checkbox
            $form.find("input[type='checkbox']").change(function(){
                var $checkbox = $(this);
                var localStorageKey = $checkbox.val() + " checked in " + $form.data("year");

                if ($checkbox.is(":checked"))
                {
                    localStorage.setItem(localStorageKey, "1");
                }
                else
                {
                    localStorage.removeItem(localStorageKey);
                }
            });

            $form.find("input[type='checkbox']").each(function(){
                var $checkbox = $(this);
                var localStorageKey = $checkbox.val() + " checked in " + $form.data("year");

                if (localStorage.getItem(localStorageKey))
                {
                    $checkbox.attr("checked", "checked");
                }
            });

            // Radio
            $form.find("input[type='radio']").change(function(){
                var $radio = $(this);
                var localStorageKey = $radio.attr("name") + "=" + $radio.val() + " checked in " + $form.data("year");

                if ($radio.is(":checked"))
                {
                    localStorage.setItem(localStorageKey, "1");
                }
                else
                {
                    localStorage.removeItem(localStorageKey);
                }
            });

            $form.find("input[type='radio']").each(function(){
                var $radio = $(this);
                var localStorageKey = $radio.attr("name") + "=" + $radio.val() + " checked in " + $form.data("year");

                if (localStorage.getItem(localStorageKey))
                {
                    $radio.attr("checked", "checked");
                }
            });

            var radioNames = [];    
            $form.find("input[type='radio']").each(function(){
                var $radio = $(this);
                var name = $radio.attr("name");
                if (radioNames.indexOf(name) == -1)
                {
                    radioNames.push(name);
                }
            });
            $.each(radioNames, function(i, name){
                var selector = "input[type='radio'][name='" + name + "']";
                if (!$form.find(selector + ":checked").length)
                {
                    $form.find(selector + ":first").prop("checked", true);
                }
            });

            // Validation
            if ($form.find("input[type=text]").length)
            {
                $form.on("submit", function(){
                    var ok = true;
                    $form.find("input[type=text]").each(function(){
                        if (isNaN(parseInt($(this).val())))
                        {
                            $(this).focus();
                            ok = false;
                            return false;
                        }
                    });
                    if (!ok)
                    {
                        return false;
                    }
                });
            }
        }
    }

    $(".hit-parade-sorter a").click(function(){
        var $parade = $(".parade");
        var $artists = $parade.find(">div");
        var sortKey = $.camelCase($(this).attr("href"));
        $artists.sort(function(a, b){
            a = -parseFloat($(a).data(sortKey));
            b = -parseFloat($(b).data(sortKey));

            if (a > b)
            {
                return 1;
            }
            if (a < b)
            {
                return -1;
            }
            return 0;
        });
        $parade.find(">div").remove();
        $artists.each(function(i, artist){
            $(artist).find("span").text(i + 1);
        });
        $parade.append($artists);
        $(".hit-parade-sorter li").removeClass("active");
        $(this).parent().addClass("active");
        return false;
    });

    /*
    ##     ##  ######  ######## ########   ######  ########  
    ##     ## ##    ## ##       ##     ## ##    ## ##     ## 
    ##     ## ##       ##       ##     ## ##       ##     ## 
    ##     ##  ######  ######   ########  ##       ########  
    ##     ##       ## ##       ##   ##   ##       ##        
    ##     ## ##    ## ##       ##    ##  ##    ## ##        
     #######   ######  ######## ##     ##  ######  ##        
    */

    $("#devices").on("change keyup keydown", function(){
        var $devices = $(this);
        var match = $devices.val().match(/\n/g);
        var length = match ? match.length : 0;
        $devices.attr("rows", length + 2);
    }).trigger("change");

    $.each({
        "#twitter_track_repeats": ".form-group:has(#twitter_repeats_min_count), .checkbox:has(#twitter_post_repeat_start)",
        "#twitter_win_artist_races" : ".form-group:has(#twitter_artist_races_min_count)",
        "#twitter_track_artist_anniversaries" : ".form-group:has(#twitter_track_artist_anniversaries_min_count)",
    }, function(parentSelector, childrenSelector){
        $(parentSelector).on("change", function(){
            var $children = $(childrenSelector);

            if ($(this).is(":checked"))
            {
                $children.show();
            }
            else
            {
                $children.hide();
            }
        }).trigger("change");
    });
});
